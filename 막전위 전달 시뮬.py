import sys
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QSlider, QLabel, QPushButton, QStackedWidget)
from PyQt6.QtCore import Qt, QTimer

# =====================================================================
# 1. 메인 허브 (Main Hub / Launcher)
# =====================================================================
class MainHub(QWidget):
    def __init__(self, parent_stack):
        super().__init__()
        self.stack = parent_stack
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("MakJunWe Simulator")
        title.setStyleSheet("font-size: 26px; font-weight: bold; margin-bottom: 40px; color: #1A237E;")
        layout.addWidget(title)

        btn1 = QPushButton("1. 실시간 축삭 전도 시뮬레이터 (Dynamic)")
        btn1.setStyleSheet(self.btn_style("#2196F3"))
        btn1.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        layout.addWidget(btn1)

        btn2 = QPushButton("2. 정적 비교 분석 시뮬레이터 (Static Overlay)")
        btn2.setStyleSheet(self.btn_style("#FF9800"))
        btn2.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        layout.addWidget(btn2)

        self.setLayout(layout)

    def btn_style(self, color):
        return f"background-color: {color}; color: white; font-size: 16px; font-weight: bold; padding: 18px; border-radius: 8px; margin: 5px;"


# =====================================================================
# 2. 시뮬레이터 1: 실시간 동적 (무감쇄 연쇄 발화 증폭 모델)
# =====================================================================    
class DynamicSimul(QWidget):
    def __init__(self, parent_stack):
        super().__init__()
        self.stack = parent_stack
        
        # 시뮬레이션 물리 시간 정의
        self.dt = 0.1
        self.time_steps = 300
        self.v_history = np.full((4, self.time_steps), -65.0)
        self.t_history = np.linspace(-self.time_steps * self.dt, 0, self.time_steps)
        
        # 4개 구간 뉴런 생체 변수 (A, B, C, D)
        self.v = np.full(4, -65.0)
        self.u = self.v * 0.2
        
        # [핵심 개혁] 각 마디 사이의 화학적 시냅스/부스터 자극 저장소 (지속성 자극)
        # 앞마디가 터지면 뒷마디의 이 저장소에 전류가 충전되고, 리셋되더라도 서서히 방출됨 (역류 방지)
        self.synaptic_current = np.zeros(4)
        
        # 외부 트리거 자극 변수
        self.stim_intensity = 0
        self.stim_duration_counter = 0  
        
        self.init_ui()
        
        # 15ms 주기의 실시간 메인 루프 가동
        self.timer = QTimer()
        self.timer.timeout.connect(self.run_simulation)
        self.timer.start(15)

    def init_ui(self):
        layout = QVBoxLayout()
        
        # 그래프 배경 흰색('w') 설정
        self.graph = pg.PlotWidget(title="Real-time Axon Conduction (Non-attenuated Active Propagation)")
        self.graph.setBackground('w')
        self.graph.setYRange(-90, 40)
        self.graph.addLegend()
        
        # 지정 색상: 빨강(A), 노랑(B), 초록(C), 파랑(D)
        colors = ['r', '#FFCC00', 'g', 'b'] 
        labels = ['Axon A (1cm)', 'Axon B (2cm)', 'Axon C (3cm)', 'Axon D (4cm)']
        
        self.curves = []
        for i in range(4):
            curve = self.graph.plot(pen=pg.mkPen(colors[i], width=2.5), name=labels[i])
            self.curves.append(curve)
        
        # 검은색 역치 점선 (-55mV)
        self.graph.addItem(pg.InfiniteLine(pos=-55, angle=0, pen=pg.mkPen('k', style=Qt.PenStyle.DashLine)))
        
        # 컨트롤 패널 디자인
        ctrl = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 20)  
        self.label_intensity = QLabel("설정된 자극 세기: 0 pA")
        
        self.btn_trigger = QPushButton("⚡ Trigger")
        self.btn_back = QPushButton("⬅ Home")
        
        self.slider.valueChanged.connect(self.update_slider_label)
        self.btn_trigger.clicked.connect(self.trigger_stimulation)
        self.btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        
        ctrl.addWidget(self.label_intensity); ctrl.addWidget(self.slider)
        ctrl.addWidget(self.btn_trigger); ctrl.addWidget(self.btn_back)
        layout.addWidget(self.graph); layout.addLayout(ctrl)
        self.setLayout(layout)

    def update_slider_label(self):
        self.stim_intensity = self.slider.value()
        self.label_intensity.setText(f"설정된 자극 세기: {self.stim_intensity} pA")

    def trigger_stimulation(self):
        # 자극 지속시간을 25ms(250스텝)로 주어 A의 확실한 연속 발화 유도
        self.stim_duration_counter = 250

    def run_simulation(self):
        # 1. 외부 자극 입력 (오직 A에게만)
        current_stim = self.stim_intensity if self.stim_duration_counter > 0 else 0
        if self.stim_duration_counter > 0:
            self.stim_duration_counter -= 1
            
        current_I = np.zeros(4)
        current_I[0] = current_stim

        # 2. 독립적인 이치케비치 연산 (서로 간의 수식 간섭/역류 전면 차단)
        for i in range(4):
            dv = (0.04 * self.v[i]**2 + 5 * self.v[i] + 140 - self.u[i] + current_I[i]) * self.dt
            du = (0.02 * (0.2 * self.v[i] - self.u[i])) * self.dt
            
            self.v[i] += dv
            self.u[i] += du
            
            # 3. [교정] 순수 인과관계 도미노 트리거 작동
            # 앞 뉴런이 정점(30)에 도달해 '쾅' 터지는 바로 그 순간! 
            # 뒷 뉴런의 전압을 역치(-55)를 확실히 뚫는 안전지대(-40mV)로 강제 예열시킴
            if self.v[i] >= 35: 
                self.v[i] = -80.0
                self.u[i] += 7.2
            
                
                # 역류나 타이밍 꼬임 없이, 오직 '순방향'으로만 도미노 신호 전달
                if i < 3:
                    self.v[i+1] = -40.0  # 뒷마디를 강제로 역치 위로 점프시켜 무조건 발화 유도
            
            # 4. 그래픽 데이터 업데이트
            self.v_history[i] = np.roll(self.v_history[i], -1)
            self.v_history[i, -1] = self.v[i]
            self.curves[i].setData(self.t_history, self.v_history[i])


# =====================================================================
# 3. 시뮬레이터 2: 부동적/정적 분석 (Static Trace Overlay)
# =====================================================================
class StaticSimul(QWidget):
    def __init__(self, parent_stack):
        super().__init__()
        self.stack = parent_stack
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        self.graph = pg.PlotWidget(title="Static Comparison (Trace Overlay)")
        self.graph.setBackground('w')
        self.graph.addLegend()
        self.graph.setLabel('bottom', "Time (ms)")
        self.graph.setYRange(-90, 40)
        
        ctrl = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 60)
        self.label_intensity = QLabel("Intensity: 0 pA")
        
        self.btn_trigger = QPushButton("📊 Trace Trigger")
        self.btn_reset = QPushButton("🧹 Clear All")
        self.btn_back = QPushButton("⬅ Home")
        
        self.slider.valueChanged.connect(lambda v: self.label_intensity.setText(f"Intensity: {v} pA"))
        self.btn_trigger.clicked.connect(self.calculate_static_trace)
        self.btn_reset.clicked.connect(self.graph.clear)
        self.btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))

        ctrl.addWidget(self.label_intensity); ctrl.addWidget(self.slider)
        ctrl.addWidget(self.btn_trigger); ctrl.addWidget(self.btn_reset); ctrl.addWidget(self.btn_back)
        layout.addWidget(self.graph); layout.addLayout(ctrl)
        self.setLayout(layout)

    def calculate_static_trace(self):
        I_val = self.slider.value()
        duration = 1000 
        t = np.linspace(0, 100, duration)
        v = -65.0; u = v * 0.2; dt = 0.1
        results = []
        
        for _ in range(duration):
            dv = (0.04*v**2 + 5*v + 140 - u + I_val)*dt
            v += dv; u += (0.02*(0.2*v - u))*dt
            if v >= 30: results.append(30); v = -65.0; u += 8.0
            else: results.append(v)
        
        color = (np.random.randint(0, 180), np.random.randint(0, 180), np.random.randint(0, 180))
        self.graph.plot(t, results, pen=pg.mkPen(color, width=2), name=f"I={I_val} pA")


# =====================================================================
# 4. 프로그램 런처 메인 윈도우 컨트롤
# =====================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    stack = QStackedWidget() 
    
    hub = MainHub(stack)
    sim1 = DynamicSimul(stack)
    sim2 = StaticSimul(stack)
    
    stack.addWidget(hub)   
    stack.addWidget(sim1)  
    stack.addWidget(sim2)  
    
    stack.setCurrentIndex(0)
    stack.setWindowTitle("NeuroSim Complete Version")
    stack.resize(1100, 650)
    stack.show()
    sys.exit(app.exec())
