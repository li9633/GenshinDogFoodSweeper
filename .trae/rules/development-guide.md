---
alwaysApply: true
---

# 项目开发规范

> **技术栈**：Python >= 3.13.7 + PySide6 >= 6.7 + PaddleOCR 3.0（PaddlePaddle 3.0.x）+ OpenCV(headless) + SQLite(WAL) + loguru
> **版本**：v3.0（2026-09-14 重写：遍历骨架 / 分层与导入根 / 后台任务托管 三件事落地后按现状校准）
>
> **图例**：✅ = **已落地**（有代码或测试兜底，违反会挂测试或线上崩）；🎯 = **期望**（尚未落地，写新代码时不要假设它已存在）

---

## 0. 先读这一页

### 0.1 六条硬规则（✅ 全部有测试或代码兜底）

| # | 规则 | 兜底 |
|---|------|------|
| 1 | 导入根只有一个：`backend.*` / `common.*`，禁止 `from ui.x import y` 这类短写 | `tests/test_architecture_guards.py` |
| 2 | 上层依赖下层；**只有 `backend/main.py` 能 import `backend.ui`** | `tests/test_layering_guards.py` |
| 3 | 逐格遍历（点格子 / 读详情 / 翻页）**不要自己写循环**，写 `SweepPolicy` + 端口装配 | `backend/automation/sweep.py` 的骨架 + 三个功能为证 |
| 4 | 后台任务交给 `WorkerHost`；结果信号用业务名，**不得覆盖 `QThread.finished`** | `WorkerHost.start()` 会拒绝违规 Worker + `tests/test_worker_host.py` |
| 5 | QML 不写业务逻辑、不拼字符串；展示文案由 Presenter 用 `Property` 给出 | 见 §4.3 |
| 6 | Presenter 里不许 `sleep`；耗时操作必须离开 UI 线程 | 清理流程曾因主线程 `time.sleep(2.5s)` 冻结界面 |

### 0.2 与 v2.0 的差异（旧文档已过时的地方）

| 旧文档的说法 | 现在的事实 |
|---|---|
| 目录树里有 `di/`、`config/`、`api_client/` | 不存在。组合根是 `backend/main.py` + `backend/ui/presenters/registry.py`；配置在 SQLite（`SettingsManager`）；HTTP 调用散在 `backend/crawler/`、`backend/features/update/` ✅ |
| 依赖注入容器 `DependencyContainer` | 🎯 未落地。现状：`registry.py` 集中声明 Presenter 工厂，依赖在 `__init__` 里手工装配 |
| `utils/screen_capture.py` | 已迁到 `backend/automation/screen_capture.py`；`utils/` 只剩 logger / log_bridge / settings_manager / qml_url ✅ |
| `async_runner.py` 是统一异步接口 | 该文件**无人使用**，实际统一接口是 `WorkerHost` + 业务 Worker ✅（`AsyncRunner` 保留但不要用） |
| `models/` 里只有 Entity + DTO | 还有 `scan_models.py`（扫描请求 / 元数据 / 停止原因）；纯逻辑另有 `backend/domain/` ✅ |
| 测试目录 `tests/unit/` + `tests/integration/` | 现状是**扁平** `tests/`，重点是"假端口跑完整流程"，不依赖游戏窗口 ✅ |
| `black` + `mypy` 强制 | 只有 `ruff`；pytest 配置在 `pyproject.toml` ✅ |

---

## 1. 快速迁移指南：Vue3 + Spring Boot → PySide6

| Vue3 / Spring Boot 概念 | PySide6 对应物 | 本项目落地位置 | 关键差异 |
| :--- | :--- | :--- | :--- |
| `App.vue` / `main.ts` | 组合根 `main()` | `backend/main.py` | 创建 QApplication、装异常过滤器、注册 Presenter、加载 QML、注册 `OnWindowReady` |
| Vue SFC (`.vue`) | QML (`.qml`) | `backend/ui/qml/{pages,components,GenshinUI}` | 没有 `<script setup>`，响应式靠 `Property + notify` |
| Pinia Store / Composables | Presenter (QObject) | `backend/ui/presenters/` | 对标 Pinia，但必须用 `@Slot` 接收 UI 事件 |
| `ref` / `reactive` | `@Property(type, notify=signal)` | 各 Presenter 类 | Qt 的响应式是**显式通知**，不自动追踪；漏 emit = 界面不刷新 |
| `watch` / `computed` | `Signal` + 手动 `emit` | 各 Presenter 类 | 没有 `computed`，派生文案写在 `Property` getter 里 |
| `@Emit` | `Signal.emit()` | 各 Presenter 类 | 信号是类型安全的（定义时写参数类型） |
| Axios / Fetch | `requests`（在后台线程里跑） | `backend/crawler/`、`backend/features/update/` | **禁止**在 UI 线程发起网络请求；🎯 统一 `api_client/` 层未落地 |
| Spring `@Service` | 纯 Python 类 | `backend/automation/`、`backend/domain/`、`backend/features/`、`backend/crawler/` | 不继承 QObject、不依赖 Qt（例外：`ocr_worker`、遍历骨架的通知回调） |
| Spring `@Repository` / JPA | Repository 类 + SQLite | `backend/database/repository/` | `with get_db("app.db") as conn:`，无 ORM |
| Spring `@Autowired` / IoC | 构造函数注入 | 各 Presenter 的 `__init__` + `backend/ui/presenters/registry.py`（集中装配） | 手工装配；🎯 `DependencyContainer` 未落地 |
| `@Async` / `@Scheduled` | `QThread` + `WorkerHost`、常驻 `OcrWorker` | `backend/ui/presenters/worker_host.py`、`backend/automation/ocr_worker.py` | UI 线程不能阻塞 |
| Vue Router | `NavigationPresenter` + QML 页面栈 | `backend/ui/presenters/navigation_presenter.py` | 路由注册集中在 `NavigationPresenter.register(...)` |
| `@Transactional` | `get_db()` Context Manager | `backend/database/connection.py` | `with get_db("app.db") as conn:` 自动 commit/rollback/close |
| Global Error Handler (Vue) | `sys.excepthook` + QML 错误回调 | `backend/exceptions/automation/exception_handler.py` | 过滤器**必须由入口显式安装**（导入即生效是禁止的） |
| `.env` / `application.yml` | `SettingsManager`（SQLite `settings` 表） | `backend/utils/settings_manager.py` | 🎯 `config/settings.yaml` + pydantic-settings 未落地 |
| ESLint / Prettier | `ruff` | `pyproject.toml` | 只有 ruff；🎯 black / mypy 未引入 |
| Vite HMR | — | — | 社区版无 QML 热重载，改 QML 要重启 `backend/main.py` |

### 思维转换要点

1. **没有虚拟 DOM** —— QML 绑定是直接求值，性能好但更容易出 Bug（尤其是越写越长的绑定表达式）
2. **没有浏览器事件循环** —— Qt 有自己的事件循环，`asyncio` **不会自动被驱动**
3. **GIL 依然存在** —— 多线程只解决"不卡界面"，纯 Python 的 CPU 密集任务不会变快
4. **UI 线程 = 主线程** —— 任何超过 ~16ms 的同步操作都会掉帧；分页 OCR 那种秒级操作必须丢到线程里

---

## 2. 架构总览

### 2.1 分层与依赖方向（✅ 由测试兜底）

```
        QML (View)            只渲染 / 只绑定 / 只转发用户操作
            │ Property · Signal · Slot
      Presenter (QObject)     backend/ui/presenters/**        状态 + 展示文案 + 调度
            │
  功能包 / 业务逻辑               backend/features/**          可插拔功能（保存格式、应用更新）
            │                    backend/automation/**        原语 + 遍历骨架 + 端口适配器
            │                    backend/domain/**            纯逻辑（文本解析、去重）
            │                    backend/crawler/**           网络抓取
            │                    backend/database/**          Repository + 连接
            ▼
   契约与模型                     backend/contracts/**         接口 / 端口 / 协议（只依赖 models）
                                backend/models/**            Entity + DTO + 枚举（无 Qt、无 IO）
```

规则：

| 规则 | 说明 | 兜底 |
|------|------|------|
| 唯一入口装配 UI | 只有 `backend/main.py` 可以 import `backend.ui`；其余模块一律不碰 UI | `tests/test_layering_guards.py` |
| 底层不依赖上层 | `backend/models`、`backend/contracts` 不得 import automation / features / domain / crawler / database / exceptions / ui | `tests/test_layering_guards.py` |
| 契约不依赖实现 | `backend/contracts/*` 只 `Protocol` + `dataclass`，不 import 任何实现 | 同上 |
| 异常不依赖 UI | `backend/exceptions/**` 只承载消息，禁止 `backend.ui`、禁止弹窗 | `tests/test_architecture_guards.py` |
| `domain` 可只读查库 | `domain/artifact_parser.py` 会查套装名（只读），不要在里面写业务编排 | — |

### 2.2 导入根：一律 `backend.*`（✅）

```python
# ✅ 正确
from backend.automation.sweep import ListSweep, SweepObserver
from backend.utils.settings_manager import settings
from common.paths import ENGINES          # common/ 是同级顶层包，直接用

# ❌ 禁止：短写顶层包
from automation.sweep import ListSweep
from utils.settings_manager import settings
```

**为什么**：项目是 editable 安装（`.venv` 里的 `.pth` 把仓库根挂上 `sys.path`），
`backend/utils/settings_manager.py` 既能被 `backend.utils.settings_manager` 导入、也能被
`utils.settings_manager` 导入 —— 后者会让同一份代码被加载**两次**，于是单例分裂、
`isinstance` 判定失败、枚举不相等。这个坑真出现过（settings 出现两份缓存），
现在由 `tests/test_architecture_guards.py::test_settings_singleton_is_shared` 看着。

### 2.3 组合根：`backend/main.py`（✅）

`main.py` 只做装配，不含业务：

1. 设置 `QT_QUICK_CONTROLS_STYLE`、创建 `QGuiApplication`、`setup_logging()`
2. `install_exception_filters()`（显式安装全局异常过滤器）
3. 创建 QML 引擎 → `registry.register_all(engine)`（所有 Presenter 在此注册为 ContextProperty）
4. 加载 `common.paths.QML_DIR` 下的主 QML
5. 注册 `OnWindowReady`：OCR 初始化等"窗口出现后才做"的事情
6. 托盘、退出清理

新增 Presenter 的姿势见 §4.2。

### 2.4 契约的判定标准（✅）

> 一个接口该放 `backend/contracts/` 还是留在功能包里？

| 判据 | 结论 |
|------|------|
| 被 **2 个及以上**功能引用 | 提到 `backend/contracts/` |
| 只被 **1 个**功能引用 | 留在该功能包内（例：`ClickOnlyPolicy` 留在调试面板模块里） |
| 是纯数据载体、跨层都要用 | 放 `backend/models/` |

### 2.5 真实目录树（✅）

```
backend/
├── main.py                      # 组合根（唯一 import UI 的非 UI 模块）
├── server.py                    # 🎯 2.0 占位：FastAPI 应用（未接入桌面端）
├── api/                         # 🎯 2.0 占位：FastAPI 路由 + uvicorn 启动器
├── contracts/                   # 接口层（Protocol / dataclass，零实现依赖）
│   ├── sweep.py                 # 遍历端口 + SweepPolicy + SweepTiming + SlotContext
│   └── artifact_save.py         # ArtifactSaver / SaveTarget / SaveResult / ScanDataset
├── models/                      # Entity + DTO + 枚举（无 Qt、无 IO）
│   ├── artifact.py              # ArtifactInfo / ArtifactStat（OCR 结果 DTO）
│   ├── artifact_set.py          # ArtifactSet（Entity）
│   ├── artifact_piece.py        # ArtifactPiece（Entity）
│   ├── slot_models.py           # SlotObject / DetectResult / SlotDetectorConfig
│   ├── scan_models.py           # FullScanRequest / ScanMeta / StopMode / StopReason
│   ├── dogfood_rule.py          # 狗粮规则模型
│   └── template.py              # 模板元数据
├── domain/                      # 纯逻辑（可被 automation / 测试直接导入）
│   ├── artifact_parser.py       # OCR 文本 → ArtifactInfo
│   └── artifact_deduplicator.py # 同位置重复识别判定
├── automation/                  # 原语 + 遍历骨架
│   ├── sweep.py                 # ⭐ SlotSweep / ListSweep / BaseSweepPolicy / SweepObserver
│   ├── sweep_adapters.py        # ⭐ 把原语接到端口上（ScreenSource / Pointer / Finder / Reader / Navigator）
│   ├── artifact_scanner.py      # 扫描功能（ScanPolicy + 首尾锚点 + 保存）
│   ├── artifact_locker.py       # 锁定功能（LockPolicy + 锁定/解锁动作）
│   ├── artifact_decomposer.py   # 清理功能（DecomposePolicy + 两阶段确认）
│   ├── scan_stop_policy.py      # 扫描停止条件（尾锚点 / 背包数量 / 固定数量）
│   ├── anchor_locator.py        # 锚点定位与展示格式化
│   ├── artifact_recognizer.py   # OCR 文本 → 圣遗物（识别器，非 Presenter）
│   ├── slot_detector.py         # 🔒 冻结：格子检测
│   ├── page_scroller.py         # 🔒 冻结：翻页
│   ├── slider_scroller.py       # 🔒 冻结：滑轨拖动
│   ├── smart_scroller.py        # 🔒 冻结：智能滚到底
│   ├── screen_capture.py        # 截图（win32 PrintWindow）
│   ├── window_helper.py         # 找窗口 / 聚焦 / 坐标原点
│   ├── mouse_controller.py      # 鼠标点击 / 滚轮
│   ├── template_manager.py      # 模板文件读写
│   ├── template_matcher.py      # 多尺度模板匹配
│   ├── ocr_engine.py            # PaddleOCR 封装（引擎实例只在 OCR 线程创建）
│   ├── ocr_worker.py            # 常驻 OCR 专用线程 + 任务队列
│   ├── ocr_model_manager.py     # 模型文件检查 / 下载
│   ├── ocr_initializer.py       # 窗口就绪后检查模型并启动 Worker（不依赖 UI）
│   ├── hotkey_listener.py       # 全局热键（实例在 registry 里 wire 到 Presenter）
│   └── ...
├── features/                    # 可插拔功能包
│   ├── artifact_save/           # 扫描结果保存：注册表 + SaveJob + 格式实现
│   │   └── formats/gdfs.py      # GDFS-v1.0（默认，基础）/ GDFS-v1.0-full（无损）
│   └── update/app_updater.py    # 应用自更新（GitHub Releases）
├── crawler/                     # 爬虫（BBS 套装数据、图标、版本检查）
├── database/
│   ├── connection.py            # get_connection() / get_db()（WAL + 外键）
│   ├── init_db.py               # 建表
│   └── repository/              # 每表一个 Repo，只返回实体
├── exceptions/
│   ├── automation/              # 自动化层异常 + 全局过滤器安装函数
│   └── api/                     # 🎯 2.0 占位
├── utils/                       # 通用工具（很薄）
│   ├── logger.py                # loguru 配置 + 标准 logging 拦截
│   ├── log_bridge.py            # 日志 → 状态栏
│   ├── settings_manager.py      # 设置读写（含 `_DEFAULTS` 注册表）
│   └── qml_url.py               # file:// URL ↔ 本地路径
└── ui/
    ├── presenters/              # Presenter 层（QObject）
    │   ├── registry.py          # ⭐ Presenter 注册表（工厂 + 信号 wire）
    │   ├── worker_host.py       # ⭐ 后台任务生命周期托管
    │   ├── rule_display.py      # 规则卡片的展示文案（Presenter 共用）
    │   ├── artifact_scan_presenter.py / artifact_locker_presenter.py / artifact_decompose_presenter.py
    │   ├── settings_presenter.py / update_presenter.py / version_check_presenter.py
    │   ├── rule_presenter.py / navigation_presenter.py / status_bar_presenter.py / title_bar_presenter.py
    │   ├── game_detector.py / image_provider.py / window_presenter.py
    │   └── debug_panel/         # 调试面板 Presenter（识别 / 元素检测 / 区域标记 / 滚动 / 输入 / 基础设施）
    ├── lifecycle.py             # OnWindowReady 注册制
    ├── gmessagebox.py           # Python → QML 弹窗桥
    ├── tray.py                  # 托盘
    ├── managers/                # 主题 / 状态栏 / 页面导航
    ├── widgets/                 # 少量 QWidget（截图预览、侧边栏）
    └── qml/                     # QML：pages/ + components/ + GenshinUI/（自绘基础控件）
```

其他顶层目录：

| 目录 | 用途 |
|------|------|
| `common/` | 跨层共享的常量 / 路径 / 版本 / 环境（`paths.ROOT/DATA/ENGINES/SCAN_RESULT/QML_DIR`） |
| `tests/` | 扁平 pytest 测试（见 §12） |
| `build_support/` | 打包脚本（PyInstaller + 安装包） |
| `installer/` | 安装器（独立的小 QML 应用） |
| `simulators/` | `update_gui.py`：模拟更新 API 的界面，用于联调更新流程 |
| `frontend/` | 🎯 2.0 占位：Vue3 前端（未接入） |
| `docs/` | 设计文档（**被 .gitignore 忽略**，不进版本库） |

---

## 3. 数据模型层（`models/` + `domain/`）

### 3.1 对象思维，禁止裸 dict 跨模块传业务数据（✅）

```python
@dataclass
class ArtifactStat:
    name: str
    value: float
    is_percentage: bool

@dataclass
class ArtifactInfo:
    set_name: str | None = None
    piece_type: str | None = None
    rarity: int | None = None
    main_stat: ArtifactStat | None = None
    sub_stats: list[ArtifactStat] = field(default_factory=list)
    level: int | None = None
    is_locked: bool | None = None
```

原则：

- **Entity**（`ArtifactSet` / `ArtifactPiece`）对应数据库行，`from_row()` / `to_dict()` 成对出现
- **DTO**（`ArtifactInfo` / `ArtifactStat` / `SlotObject` / `ScanMeta`）跨层传递，**不含任何 UI 字段**
- **枚举不要用裸字符串**：`StopMode` / `StopReason` / `ArtifactRecognitionField` 这类用 `StrEnum`，
  需要展示时在枚举上加 `label` 属性，而不是在 UI 里写 `if mode == "anchor"`

### 3.2 `models/` 的额外约束（✅ 测试兜底）

- 不 import PySide6（模型层要能在没有 Qt 的环境下导入）
- 不 import `backend.database` / `backend.automation` / …（见 §2.1）
- 工厂方法放模型上：如 `FullScanRequest.from_slot_config(config, ...)`
  —— 让"模板几何参数"这类细节留在模型/配置内部，上层不重复拼装

### 3.3 `domain/` 放什么

纯函数式的业务逻辑：文本解析（`artifact_parser`）、去重判定（`artifact_deduplicator`）。
特征：**输入输出都是模型对象，没有 Qt、没有线程、没有 UI**，因此最容易写单测。

---

## 4. UI 层与 Presenter 层

### 4.1 职责划分

| 层 | 可以做什么 | 不能做什么 |
|----|-----------|-----------|
| **QML** | 渲染、绑定、动画、把用户操作转发给 `@Slot` | 写业务判断、拼展示字符串、直接调 `backend.automation.*` / `database.*` |
| **Presenter** | 接收 UI 事件、调业务层、维护 UI 状态、发射信号、组装展示文案 | 创建 UI 组件、`sleep`、在 UI 线程跑耗时操作、直接建数据库连接 |

### 4.2 新增一个页面 / Presenter（✅ 标准流程）

1. 在 `backend/ui/presenters/` 写 `XxxPresenter(QObject)`，只暴露 `Property` / `Signal` / `Slot`
2. 在 `backend/ui/presenters/registry.py` 的 `_make_registry()` 里**加一行**：

```python
from backend.ui.presenters.xxx_presenter import XxxPresenter

def _wire_xxx(p: XxxPresenter) -> None:          # 需要时才写：把全局信号接到 Presenter
    HotkeyListener.instance().stopRequested.connect(p._on_hotkey_stop)

registry.append(("Xxx", XxxPresenter, [_wire_xxx]))
```

3. 在 `backend/ui/qml/pages/` 写 `XxxPage.qml`，用 ContextProperty 名（上面的 `"Xxx"`）绑定
4. 需要路由时用 `NavigationPresenter.register(page, tab, sub)`（设置页子 Tab 就是这么注册的）
5. 需要"窗口就绪后做事"时：UI 组件继承 `OnWindowReady`；**非 UI 组件**用
   `OnWindowReady.register(callback)` 由入口显式接入（不要反向 import UI 层去继承它）

Presenter 骨架（Property 必须有 `notify`，槽只做转发）：

```python
class XxxPresenter(QObject):
    statusChanged = Signal()
    runningChanged = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._status = ""
        self._host = WorkerHost(self)                     # 有后台任务就用它
        self._host.busyChanged.connect(self.runningChanged.emit)

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=runningChanged)
    def running(self) -> bool:
        return self._host.busy

    @Slot()
    def doWork(self) -> None:
        worker = XxxWorker(...)
        worker.stepChanged.connect(self._set_status)
        worker.stepCompleted.connect(self._on_done)
        worker.errorOccurred.connect(self._on_error)
        self._host.start(worker)
```

### 4.3 QML 硬规则（✅）

```python
# ✅ Presenter 提供展示就绪的数据
@Property(str, notify=statsChanged)
def statsText(self) -> str:
    return f"锁定: {self._locked} | 解锁: {self._unlocked} | 跳过: {self._skipped}"
```

```qml
// ✅ 只显示
Text { text: ArtifactLocker.statsText }

// ❌ 禁止：QML 里拼字符串 / 做判断
Text { text: "锁定: " + ArtifactLocker.lockedCount + " | ..." }
```

其他 QML 约定：

- 文件名 `PascalCase`，属性 / id `camelCase`，信号处理函数 `on` + 信号名（`onRecognitionFinished`）
- 自绘控件放 `qml/GenshinUI/`（`GButton` / `GCard` / `GSpinBox` / `GComboBox` / `GMessageBox`…），
  颜色字体一律取自 `Theme.*`，不要在页面里写死色值
- 列表用 `ListView` + `delegate`（不要 `Column + Repeater` 铺长列表）
- `console.log` 只允许用于调布局，业务日志走 `log`

---

## 5. 业务逻辑层

### 5.1 逐格遍历骨架（⭐ 最重要的一节）

「定位列表 → 逐格点击 → 读出详情 → 判定 → 动作 → 翻页」这套骨架已经收敛成可组合单元，
**扫描器 / 锁定器 / 清理器 / 调试面板**四个使用方都基于它。新增类似功能时：

```
backend/contracts/sweep.py   ── 端口（ScreenSource / Pointer / SlotFinder / ArtifactReader / ListNavigator）
                                + SweepPolicy + SweepTiming + SlotContext + SweepSummary
backend/automation/sweep.py  ── SlotSweep（一页逐格）+ ListSweep（整轮翻页）
                                + BaseSweepPolicy（默认实现）+ SweepObserver（过程回调）
backend/automation/sweep_adapters.py ── 端口实现：WindowScreenSource / MousePointer /
                                DetectorSlotFinder / RecognizerArtifactReader / ScrollerNavigator / LockIconToggler
```

**接入姿势**：只写一个 `SweepPolicy`（需要时加 `SweepObserver`），然后装配端口跑起来。

| 钩子 | 何时调用 | 用途 |
|------|---------|------|
| `should_click(slot)` | 点击前 | 预筛（如跳过已锁定格子），省一次点击 + 一次识别 |
| `needs_detail()` | 每页开始时 | 返回 `False` = **纯点击模式**：不截图不识别，`SlotSweep` 连 `reader` 都不需要 |
| `should_read(slot, image)` | 点击并截图后、识别前 | 图像相关判断（如空格子检测） |
| `on_artifact(artifact, ctx)` | 识别成功后 | 判定与动作；返回 `False` 结束整轮 |

| 观察者回调 | 触发时机 |
|-----------|---------|
| `on_page_start(page, slots_total)` | 每页开始 |
| `on_slot_clicked(index, total, slot)` | 每点完一格（**纯点击模式也能拿到进度**） |
| `on_artifact(artifact, ctx)` | 识别成功（**早于策略判定**，会看到随后被判重丢弃的结果） |

```python
class KeepFiveStarPolicy(BaseSweepPolicy):
    """只关心五星的判定示例"""

    def should_click(self, slot: SlotObject) -> bool:
        return slot.rarity == ArtifactRarity.FIVE or slot.rarity is ArtifactRarity.UNKNOWN

    def on_artifact(self, artifact: ArtifactInfo, ctx: SlotContext) -> bool:
        self.results.append(artifact)
        return True
```

时序参数集中在 `SweepTiming`（`click_delay_s` / `detail_settle_s` / `tick_delay_ms` / `page_settle_ms`），
不要在功能里零散写 `sleep`。

**反例**：在功能里自己写 `for slot in det_result.slots: click → sleep → capture → recognize`。
（历史上扫描器 / 锁定器 / 清理器各写了一遍，共减少约 600 行重复代码。）

### 5.2 冻结模块：只许调用，不许改（🔒）

| 模块 | 内容 |
|------|------|
| `automation/slot_detector.py` | 格子检测（ROI / 网格 / 星级 / 锁定判定） |
| `automation/page_scroller.py` | 翻页 |
| `automation/slider_scroller.py` | 滑轨拖动 |
| `automation/smart_scroller.py` | 智能滚到底 |

已在游戏内反复验证。要调时序/参数，走 `SlotDetectorConfig` 或请求对象（如 `FullScanRequest`）
暴露的入口，**不要动检测/滚动算法本身**；重构时这四个文件只允许改 import 行。

### 5.3 新增功能的标准流程（查 → 引 → 造 → 装配 → 测）

#### Step 1：查（Search）

```bash
grep -rn "def capture" backend/automation/          # 原语是否已有
grep -rn "class .*Policy" backend/automation/       # 是否已有同类策略
grep -rn "class .*Repo" backend/database/repository/
grep -rn "Property" backend/ui/presenters/          # 是否已有可复用的展示逻辑
```

| 要写的东西 | 先查这里 |
|-----------|---------|
| 截图 / 点击 / 滚动 / 检测 / 识别 | `backend/automation/`（其中 4 个是冻结模块） |
| 遍历列表、点格子、翻页 | `backend/automation/sweep*.py`（**必须复用**） |
| 跨功能接口 | `backend/contracts/` |
| 数据访问 | `backend/database/repository/` |
| 通用 UI 控件 | `backend/ui/qml/GenshinUI/` |
| 后台任务 | `backend/ui/presenters/worker_host.py` |
| 设置项 | `backend/utils/settings_manager.py` 的 `_DEFAULTS` |
| 异常类型 | `backend/exceptions/automation/exceptions.py` |

#### Step 2：引（Import）

优先扩展现有实现；接口差一点就加参数或写包装，**不要复制一份**。

#### Step 3：造（Create）

新模块要求：单一职责、接口通用、无 UI 依赖（UI 相关一律进 `backend/ui/`）、可脱离游戏窗口测试。

命名：

```python
# ❌ 绑死业务
def capture_for_artifact_recognition(): ...
# ✅ 通用
def capture(window=None) -> CaptureResult | None: ...

# ❌ 名字暴露实现
def use_win32_to_get_window_handle(): ...
# ✅ 面向接口
def find_genshin_window() -> int | None: ...
```

文件名要能自解释：`recognizer.py` → `artifact_recognizer.py`（本次重构就是这么改的）；
`utils/` 这种筐不要什么都往里塞（它现在只有 4 个文件）。

#### Step 4：装配（Wire）

- 纯逻辑模块：构造函数注入依赖（可测试性优先）
- UI 相关：在 `registry.py` 注册 Presenter（§4.2）
- 后台任务：业务 Worker(`QThread`) + `WorkerHost`（§8.2）

#### Step 5：测试

见 §12：优先写"假端口驱动的流程测试"，不要依赖游戏窗口和真实 OCR。

#### Step 6：文档

改动若影响本文任何一条规范，同步更新本文 + `docs/architecture.md`。

### 5.4 Code Review 检查清单

- [ ] 导入是否全部 `backend.*` / `common.*`？（§2.2）
- [ ] 是否引入了反向依赖（下层 import 上层、非入口 import UI）？（§2.1）
- [ ] 逐格遍历是否复用了 `SlotSweep` / `ListSweep`，而不是自己写循环？（§5.1）
- [ ] 是否碰了冻结模块？（§5.2）
- [ ] 后台任务是否走 `WorkerHost`、结果信号是否用业务名？（§8.2）
- [ ] QML 里有没有拼字符串、写业务判断？（§4.3）
- [ ] 展示文案是否由 Presenter 用 `Property` 给出，且 `notify` 齐全？
- [ ] Presenter 里有没有 `sleep` / 长耗时同步调用？（§8）
- [ ] 新设置项是否加进了 `SettingsManager._DEFAULTS`？
- [ ] 新异常是否是"只带消息"的异常，且没有在 import 时做副作用？（§10）
- [ ] 日志是否用 `log`（不是 `print`）？异常分支是否带上下文？
- [ ] 是否补了测试？`ruff check` + `pytest` 是否通过？（§12）
- [ ] 契约放对地方了吗（≥2 功能才进 `contracts/`）？（§2.4）

---

## 6. 数据层（`database/`）

### 6.1 Repository 模式（✅）

```python
class ArtifactSetRepo:
    """artifact_sets 表数据访问"""

    @staticmethod
    def count() -> int: ...
    @staticmethod
    def find_all() -> list[ArtifactSet]: ...
    @staticmethod
    def upsert(entity: ArtifactSet) -> None: ...
```

- Repo **只返回实体/标量**，不返回裸 `dict` / `tuple`
- 调用方不写 SQL
- 跨表逻辑不要塞进 Repo（那是 `features/` 或 `domain/` 的事）

### 6.2 连接管理（✅）

```python
# backend/database/connection.py
with get_db("app.db") as conn:      # 自动 commit / rollback / close
    conn.execute("INSERT ...")
```

- 数据库文件在 `<项目根>/data/`（`common.paths.DATA`），如 `artifacts.db`（圣遗物数据）、`app.db`（设置 / 规则 / 日志）
- 连接创建时已 `PRAGMA journal_mode=WAL` + `foreign_keys=ON`
- **禁止**自己 `sqlite3.connect()`（绕过 WAL 与外键，且容易忘记 close）
- **禁止**把连接对象跨线程传递；每个线程各自 `with get_db(...)`

### 6.3 SQLite 并发

| 场景 | 风险 | 做法 |
|------|------|------|
| UI 线程 + 后台线程同时写 | `database is locked` | WAL 已开 + 事务尽量短 |
| 长事务 | 阻塞其他线程 | 批量写分批提交 |
| 跨线程复用连接 | 未定义行为 | 每线程独立 `get_db()` |
| 存路径/大对象 | 库膨胀 | 大文件走磁盘，库里只存路径 |

---

## 7. 命名与编码规范

### 7.1 Python（✅）

- 类 `PascalCase`（`ArtifactRecognizer`）、函数/变量 `snake_case`、私有成员前缀 `_`
- 模块名要自解释、不要与第三方包重名（`recognizer.py` → `artifact_recognizer.py`）
- 信号：**业务化命名**，读写状态用过去式/完成态（`dataChanged` / `scanCompleted` / `lockCompleted` / `checkCompleted`），
  **严禁**覆盖 Qt 内置信号名（`finished` / `error` / `started`）
- 槽（`@Slot`）：动词短语（`startScan` / `stopLock` / `toggleRuleSelection`）
- 类型注解：公开方法写全参数与返回值；用 `list[int]` / `str | None`（Python ≥ 3.13）
- 注释与文档：**中文**，说清"为什么这么做"，不要写"这行给 x 加 1"
- 文本文件一律 UTF-8 **无 BOM**（历史遗留 BOM 属可选清理项）

### 7.2 QML（✅）

见 §4.3。

### 7.3 禁止事项（汇总）

- 禁止短写顶层包导入（`from ui.x` / `from utils.x`）
- 禁止下层 import 上层；禁止非 `main.py` 模块 import `backend.ui`
- 禁止在 `import` 时产生全局副作用（装钩子、弹窗、开线程、连数据库）
- 禁止 QML 写业务逻辑 / 拼展示字符串
- 禁止 `@Property` 缺 `notify`
- 禁止 Presenter 里 `sleep` / 长时间同步调用
- 禁止覆盖 `QThread.finished`
- 禁止裸 `dict` / `list` 跨模块传业务数据
- 禁止 `print()` 代替 `log`
- 禁止绕过 `get_db()` 直接用 `sqlite3`
- 禁止硬编码绝对路径（用 `common.paths`）

### 7.4 复用原则（DRY）

新增功能前先搜索，确认没有同类实现；

```
查（搜索现有实现）→ 引（复用/扩展，不复制）→ 造（新建通用模块：单一职责 + 通用接口 + 无 UI 依赖 + 可测试）
```

反模式：

```python
# ❌ 复制粘贴
def resize_image(img, w, h): ...
def resize_image(img, width, height): ...     # 另一处又来一份

# ❌ 绕过架构：在 QML 里算业务
function checkArtifactQuality(stats) { let total = 0; ... }

# ✅ 在 Presenter 里算，QML 只显示
@Property(bool, notify=dataChanged)
def isHighQuality(self) -> bool: ...
```

### 7.5 依赖注入：现状与目标

- ✅ **现状**：构造函数注入 + `registry.py` 集中装配 + 模块级单例（`settings`、`OcrWorker.instance()`、`HotkeyListener.instance()`）
- 🎯 **目标**：`backend/di/container.py`（`DependencyContainer`）统一管理重量级资源（OCR 线程、日志桥）的生命周期，
  把 `instance()` 单例逐步收编；**新代码不要新增单例**

---

## 8. 异步与线程安全

> Qt 的 UI 线程是**单线程事件循环**。任何超过 ~16ms 的同步操作都会掉帧；
> 秒级操作会让窗口进入"无响应"。

### 8.1 PaddleOCR 线程独占（✅ 强制）

PaddleOCR 底层是 C++，引擎实例**只能在创建它的线程里用**。

- 现状：`backend/automation/ocr_worker.py` 是**继承 `QThread`** 的常驻 Worker，
  引擎在该线程内初始化，任务通过信号排队提交；`ocr_engine.py` 只负责创建/持有实例
- 调用方（Presenter / 识别器）**不得**自己 `PaddleOCR(...)`；需要识别时走 `OcrWorker`
- 🎯 期望：迁移到 `QObject + moveToThread`（更灵活，槽函数自动在子线程执行）；迁移前保持现状
- 模型没下载好时抛 `OcrModelNotReadyError`（消息型异常，由 UI 层决定怎么提示）

### 8.2 后台任务托管：`WorkerHost`（⭐ ✅）

各功能原先各自手写「起线程 → 连信号 → 结束清引用」，反复出现
`QThread: Destroyed while thread is still running` 这类静默崩溃。现在统一：

```python
from backend.ui.presenters.worker_host import WorkerHost

self._host = WorkerHost(self)
self._host.busyChanged.connect(self._on_busy_changed)   # 驱动界面"运行中"
...
worker = XxxWorker(...)                # QThread 子类
worker.stepChanged.connect(self._set_status)
worker.xxxCompleted.connect(self._on_done)   # 业务名结果信号
worker.errorOccurred.connect(self._on_error)
if not self._host.start(worker):       # 运行中会拒绝并返回 False
    ...
```

| 能力 | 说明 |
|------|------|
| `start(worker)` | 单飞：已有任务在跑时**拒绝**启动（不打断当前任务）；线程**真正结束后**才清引用并 `deleteLater` |
| `stop()` | 转发停止请求（Worker 有 `stop()` 就调，没有就是空操作） |
| `busy` / `busyChanged` | 供界面"运行中"状态；也可作为入口函数的防重入条件 |

约定：

- 结果信号用业务名（`scanCompleted` / `lockCompleted` / `selectCompleted` / `executeCompleted` / `checkCompleted`），
  **不得覆盖 `QThread.finished`** —— `WorkerHost.start()` 会检测并拒绝
- 需要"停止"能力的 Worker 自己实现 `stop()`（通常是 `threading.Event.set()`）
- 不使用托管的例外：**一个后台任务在完成回调里再起一个后台任务**的链式调用
  （调试面板 `scrollToBottom → 定位尾锚点` 就是这种）。这类代码走宿主会因宿主仍忙而被拒，
  要托管得先给宿主加排队能力 —— 🎯 未落地，先维持现状
- Presenter 里**不要** `time.sleep`：需要等待动画/间隔时用 `QTimer`
  （清理流程原先用 `time.sleep(0.1) × 25` 等分解动画，界面冻结 2.5 秒，现已改成 `QTimer`）

### 8.3 耗时操作清单

| 操作 | 耗时 | 现状 |
|------|------|------|
| PaddleOCR 推理 | 1–3s | ✅ 常驻 `OcrWorker` 线程 |
| 多尺度模板匹配 | 100–500ms | ⚠️ 由调用方放进后台线程（`_DebugWorker` / 业务 Worker），无统一封装 |
| 截图（PrintWindow） | 50–200ms | ⚠️ 同上；遍历骨架里在后台线程执行 |
| 遍历（滚动 + 点击 + 识别） | 秒~分钟 | ✅ 各功能 Worker（`FullScanWorker` / `LockWorker` / `SelectWorker` + `ExecuteWorker` / `_BatchClickWorker`） |
| 爬虫 / 版本检查 / 下载 | 秒级 | ✅ `SyncWorker` / `VersionCheckPresenter` / `_CheckWorker` / `_DownloadWorker` / OCR 模型下载 Worker |
| FastAPI（2.0） | — | 🎯 未接入 |

### 8.4 GIL 与线程模型

| 场景 | GIL 影响 | 结论 |
|------|---------|------|
| PaddleOCR / OpenCV（C++） | 推理时会释放 GIL | 专用线程即可真并行 |
| 纯 Python 图像/文本循环 | 受 GIL 限制 | 用线程只是"不卡界面"，别指望加速 |
| CPU 密集纯 Python | GIL 瓶颈 | 考虑 `multiprocessing` / `QProcess`（🎯 尚未使用） |

---

## 9. 网络与通信

### 9.1 现状（✅）

| 调用 | 位置 | 线程 |
|------|------|------|
| 圣遗物套装数据抓取（BBS） | `backend/crawler/artifact_set_fetcher.py` | `SyncWorker`（QThread） |
| 版本检查 | `backend/crawler/version_checker.py` | `VersionCheckPresenter` 的一次性任务 |
| 应用更新检查 / 下载 | `backend/features/update/app_updater.py` | `_CheckWorker` / `_DownloadWorker` |
| OCR 模型下载 | `backend/automation/ocr_model_manager.py` | 模型下载 Worker |

规则：

- 一律在后台线程里发起；UI 线程只收信号
- 超时/失败要有明确文案（Presenter 负责把错误翻成用户能看懂的话）
- 请求参数（owner/repo/URL）集中在 `features/update/app_updater.py` 的常量里，不要散落

### 9.2 🎯 期望：统一 `api_client/` 层

目的：把 HTTP 细节（base_url、超时、重试、代理）收在一处，便于替换后端（FastAPI / Spring Boot）
与 mock 测试。落地前不要新增第三套 HTTP 写法。

### 9.3 🎯 期望：环境配置

`config/settings.yaml` + `pydantic-settings` 目前**不存在**；运行期配置一律走
`SettingsManager`（见 §11）。引入 yaml 配置时需明确"哪些属于构建期/部署期、哪些属于用户设置"。

---

## 10. 全局异常与日志

### 10.1 异常是"消息载体"（✅ 测试兜底）

```python
class GameWindowNotFoundError(RuntimeError):
    """游戏窗口未找到异常"""

    _MESSAGE = WINDOW_NOT_FOUND_PROCESS_MSG

    def __init__(self, message: str = "") -> None:
        msg = message or self._MESSAGE
        super().__init__(msg)
        log.warning(msg)        # 构造时最多记一条日志
```

- 异常类**只承载消息**：不弹窗、不碰 UI、不做 IO；构造时最多 `log` 一行
- `backend/exceptions/**` 禁止 import `backend.ui`（`tests/test_architecture_guards.py` 会检查）
- **导入异常包不得产生副作用**（历史上 `import backend.exceptions.automation` 会顺手装全局钩子，
  导致测试行为漂移）—— 过滤器由入口显式安装：

```python
# backend/main.py
from backend.exceptions.automation.exception_handler import install_exception_filters
install_exception_filters()      # 幂等；重复调用保持同一处理器
```

- **用户可操作的错误**（如"OCR 模型未就绪"）由 UI 层决定怎么提示：
  `backend/ui/lifecycle.py` 里维护 `_USER_ACTIONABLE_ERRORS`，窗口就绪回调抛这类异常时弹 `GMessageBox`

### 10.2 槽与线程的异常防护

- `@Slot` 内部要自己 `try/except`：未捕获异常会让 Qt 事件循环静默崩溃（窗口还在但没反应）
- 后台 Worker 的 `run()` 必须整体 `try/except`，用 `errorOccurred` 把错误送回 UI 线程
  （参考三个功能的 Worker：`_ScanError` + `errorOccurred.emit(...)`）

```python
@Slot(str)
def onUserAction(self, text: str) -> None:
    try:
        self._service.do(text)
    except ValueError as exc:
        log.warning(f"参数不合法: {exc}")
        self._set_status(f"输入有误: {exc}")
    except Exception as exc:
        log.error(f"操作失败: {exc}", exc_info=True)
        self._set_status("操作失败，请查看日志")
```

### 10.3 日志（✅）

统一 `from backend.utils.logger import log`（loguru），禁止 `print` / 混用 `logging`。

| 级别 | 场景 | 示例 |
|------|------|------|
| `TRACE` | 极细节调试（生产关闭） | 每个采样点 |
| `DEBUG` | 开发调试 | 入参、中间结果、配置项 |
| `INFO` | 正常流程节点 | "全量扫描开始"、"OCR 引擎就绪" |
| `WARNING` | 功能受影响但可继续 | "截图失败，跳过该格"、"未检测到滑块" |
| `ERROR` | 功能性失败 | "保存失败"、"识别异常" |
| `CRITICAL` | 致命 | "PaddleOCR 初始化失败" |

Sink 现状（`backend/utils/logger.py`）：

| Sink | 级别 | 用途 |
|------|------|------|
| stderr（彩色） | 设置里的 `log.level`（默认 DEBUG） | 开发实时看 |
| `logs/app_YYYY-MM-DD.log` | DEBUG ~ INFO（`filter` 上限为 WARNING 之下） | 常规记录，按设置轮转/保留/压缩 |
| `logs/error_YYYY-MM-DD.log` | WARNING 及以上 | 出错排查 |
| 状态栏回调（`log_bridge`） | WARNING+ | 实时提示用户 |
| 标准 `logging` / uvicorn | WARNING+ | 统一转发进 loguru |

🎯 期望：日志入库（`LogRepo`）供界面内查询，目前只有状态栏桥接。

---

## 11. 配置与环境管理

### 11.1 设置项：`SettingsManager`（✅）

所有用户设置都注册在 `backend/utils/settings_manager.py` 的 `_DEFAULTS`（按命名空间分组），
首次启动会写库，读取用带类型的 getter：

```python
"scan":  {"enable_dedup": "true", "stop_mode": "anchor", "fixed_count": "0",
          "save_dir": "", "save_format": ""},
"debug": {"batch_click_interval": "100"},
```

```python
settings.get("scan.stop_mode")            # str
settings.get_bool("scan.enable_dedup")    # bool
settings.get_int("debug.batch_click_interval") or 100   # int（缺省时给兜底）
settings.set("scan.save_dir", str(path))
```

**新增设置项的固定动作**：先在 `_DEFAULTS` 加一行，再在 Presenter 里读写；不要在代码里散落魔法默认值。

### 11.2 环境变量与路径

| 项 | 说明 |
|---|---|
| `QT_QUICK_CONTROLS_STYLE` | 强制 `Basic`（自定义样式的前提），入口设置 |
| `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` | 跳过 PaddleOCR 的联网源检查（离线启动） |
| 路径 | 一律使用 `common/paths.py`（`ROOT` / `DATA` / `ENGINES` / `SCAN_RESULT` / `QML_DIR` / `TEMPLATES`…），兼容 PyInstaller 的 onefile / one-dir |
| 资源文件 | 用 `common/resources.py` 的 `Resource`，不要拼字符串路径 |

### 11.3 依赖与工具链（✅）

- 依赖在 `pyproject.toml`（PEP 621）；dev 组：`pyinstaller` / `pytest` / `ruff`
- 环境用 `uv`；editable 安装让仓库根进入 `sys.path`（所以 `backend.*` 与 `common.*` 都能直接导入）
- 质量工具：**只有 `ruff`**（`ruff check`，`lint.ignore = ["BLE001"]`：本项目统一用 `except Exception` 并自行 log + emit）
- 🎯 未引入：`black`（格式化）、`mypy`（类型检查）、`pytest-qt`

```powershell
uv run ruff check backend installer simulators tests build_support
uv run pytest
```

---

## 12. 测试规范

### 12.1 目录与运行（✅）

```
tests/
├── __init__.py
├── fakes.py                        # 共享假端口（FakeWorld / FakeScreen / FakePointer / FakeReader / FakeToggler…）
├── test_architecture_guards.py     # 导入根 / 单例 / 导入副作用
├── test_layering_guards.py         # 分层方向（只有入口能 import UI；底层不依赖上层）
├── test_slot_sweep.py              # 遍历骨架语义（含纯点击模式）
├── test_artifact_scan_policy.py    # 扫描策略：预筛 / 去重 / 停止条件
├── test_artifact_decompose_policy.py  # 清理策略：反选 / 单批上限 / 锁定物停止
├── test_scan_policy.py             # 扫描请求与停止策略
├── test_artifact_save.py           # 保存格式落盘契约
├── test_rule_display.py            # 规则卡片展示文案
├── test_dogfood_rule_engine.py     # 狗粮规则引擎判定
├── test_worker_host.py             # 后台任务托管
├── test_decompose_presenter_flow.py   # 清理流程（两阶段 + 批次循环，假 Worker）
└── test_debug_batch_click.py       # 调试面板批量点击（假端口）
```

```powershell
uv run pytest                                        # 常规
# 沙箱内（系统临时目录 / 新建目录枚举受限时）
uv run pytest -p no:cacheprovider --basetemp=temp/pytest-base
```

配置在 `pyproject.toml`：`testpaths = ["tests"]`、`addopts = "-q"`。

### 12.2 核心思路：假端口跑真实流程（✅）

遍历骨架、策略、Presenter 流程**都不需要游戏窗口**：
用 `tests/fakes.py` 的假端口替换 `ScreenSource` / `Pointer` / `SlotFinder` / `ArtifactReader`，
就能端到端验证"点了哪些格子、识别了几次、什么时候停"。

```python
def test_click_only_policy_skips_capture_and_reader() -> None:
    det = DetectResult(slots=[_slot(0), _slot(1)], bottom_y=0.0, debug_infos=())
    screen, pointer = FakeScreen(frames=[b"detail"]), FakePointer()

    sweep = SlotSweep(screen=screen, pointer=pointer, slot_finder=det, reader=None, timing=FAST)
    assert sweep.run_page(det, page=0, policy=_ClickOnly()) is True
    assert len(pointer.clicks) == 2
    assert screen.calls == 0        # 纯点击模式：一次多余的截图都没有
```

需要 Qt 的测试自己建应用对象（**未引入 `pytest-qt`**，没有 `qtbot`）：

```python
@pytest.fixture(scope="module")
def app():
    instance = QCoreApplication.instance() or QCoreApplication([])
    yield instance
```

后台 Worker 的测试用假 Worker + 事件泵：

```python
def _pump(app, predicate, timeout=5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()
```

### 12.3 测试要覆盖什么

- **架构约束**：导入根、分层方向、导入无副作用（新增约束时**先加守卫测试**）
- **策略与骨架**：预筛、停止条件、翻页、纯点击模式（用假端口）
- **Presenter 流程**：状态机（如清理的两阶段 + 批次循环）、信号时序、防重入
- **落盘契约**：保存格式的字段（`GDFS-v1.0` 只丢 `raw_texts`，`-full` 无损）

不写什么：真实 OCR、真实截图、需要游戏窗口的用例（这类只能人工验证，改动前后各跑一次真机流程）。

### 12.4 🎯 期望

- `tests/unit` + `tests/integration` 分层、`pytest-qt`（`qtbot.waitSignal`）、覆盖率门槛、CI 自动跑
  —— 目前都没有，靠 `ruff check` + `pytest` 本地把关

---

## 13. 性能优化

### 13.1 已知瓶颈与现状

| 瓶颈 | 耗时 | 现状 / 做法 |
|------|------|------------|
| PaddleOCR 冷启动 | 3–5s | ✅ 启动后在后台线程异步加载（窗口就绪即开始预热），不阻塞界面 |
| 多尺度模板匹配 | 100–500ms | ⚠️ 依赖调用方放进后台线程 |
| 截图（PrintWindow） | 50–200ms | ⚠️ 同上；遍历骨架中每格一次，属必要开销 |
| 长列表渲染 | 卡顿 | ✅ 用 `ListView` + `delegate`（`cacheBuffer` 预取） |
| SQLite 写入 | 偶尔锁 | ✅ WAL + 短事务 |
| 连续点击/翻页 | 累积延迟 | ✅ 由 `SweepTiming` 统一调档（`click_delay_s` / `tick_delay_ms` / `page_settle_ms`） |

### 13.2 QML 性能

```qml
// ✅ 懒加载
ListView { model: artifactModel; delegate: ArtifactItem {}; cacheBuffer: 200 }

// ❌ 一次性创建所有项
Column { Repeater { model: artifactModel; delegate: ArtifactItem {} } }
```

另外：绑定表达式保持短小（复杂计算放 Presenter）；避免在 `onXxx` 里做重活；
大图用 `Image.asynchronous: true`。

---

## 14. Git 提交规范

提交信息：`type(scope): 中文描述`（首行不超过 ~50 字，细节写在正文）

| type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修 Bug |
| `refactor` | 重构（行为不变） |
| `style` | 格式 / 注释 / 命名规范化 |
| `chore` | 构建、依赖、配置 |
| `test` | 测试 |
| `docs` | 文档 |

例：

```
refactor(遍历骨架): 抽出 SlotSweep / ListSweep 与端口适配器
feat(保存): 可插拔的扫描结果保存格式
fix(更新): 修复下载进度条不刷新（绑定短路 + 未 emit downloadTotalChanged）
```

约定：

- 一次提交只做一件事；大型重构**先开分支**，按"结构 / 契约 / 功能 / UI / 测试"分批提交
- 提交前：`ruff check` + `pytest` 必须通过
- 不要提交 `data/`、`logs/`、`dist/`、`engines/`、`scan_result/`、`temp/`（已在 `.gitignore`）
- `docs/` 被忽略（设计文档不进库）；规范与架构说明以 `.trae/rules/development-guide.md` 与代码注释为准

---

## 附录 A：运行时架构图（✅ 现状）

```
                        backend/main.py  (组合根)
        ┌──────────────────────────────────────────────────────────┐
        │ setup_logging() · install_exception_filters()            │
        │ QGuiApplication + QQmlApplicationEngine                  │
        │ registry.register_all(engine)   ←── 所有 Presenter 工厂    │
        │ OnWindowReady.register(OCR 初始化)                        │
        └───────────────┬──────────────────────────────────────────┘
                        │ setContextProperty (QML 只认这些名字)
        ┌───────────────▼──────────────────────────────────────────┐
        │ backend/ui/qml/**   pages · components · GenshinUI        │
        └───────────────┬──────────────────────────────────────────┘
                        │ Property / Signal / Slot
        ┌───────────────▼──────────────────────────────────────────┐
        │ Presenters (QObject)                                      │
        │  ArtifactScan · ArtifactLocker · ArtifactDecompose        │
        │  Rule · Settings · Update · VersionCheck · Navigation …   │
        │  └── WorkerHost ──► QThread Worker（业务名结果信号）       │
        └───────────────┬──────────────────────────────────────────┘
                        │ 调用（单向）
        ┌───────────────▼──────────────────────────────────────────┐
        │ features/ (保存格式 · 应用更新)                            │
        │ automation/ (遍历骨架 · 原语 · 冻结模块 · OcrWorker)        │
        │ domain/ (解析 · 去重)   crawler/ (抓取)   database/ (Repo) │
        └───────────────┬──────────────────────────────────────────┘
                        │ 只依赖
        ┌───────────────▼──────────────────────────────────────────┐
        │ contracts/ (端口 / 协议)   models/ (Entity / DTO / 枚举)   │
        └──────────────────────────────────────────────────────────┘
```

## 附录 B：技术栈速查

| 技术 | 版本 | 用途 | 对标 |
|------|------|------|------|
| Python | >= 3.13.7 | 主力语言 | Java 17+ |
| PySide6 | >= 6.7 | GUI（QML + QObject） | Vue 3 + DOM |
| PaddleOCR / PaddlePaddle | >= 3.0 / 3.0.x | 文字识别 | Tesseract |
| OpenCV (headless) | >= 4.10 | 图像处理 / 模板匹配 | PIL |
| NumPy | >= 2.0 | 数组运算 | — |
| loguru | >= 0.7 | 日志 | Logback |
| SQLite | 内置（WAL） | 本地数据库 | H2 |
| requests | >= 2.32 | HTTP（爬虫 / 更新 / 模型下载） | Axios |
| rapidfuzz | >= 3.0 | 模糊匹配（套装名纠错） | — |
| pydirectinput / pyautogui / pynput | — | 键鼠与热键 | — |
| pywin32 | >= 308 | 窗口句柄 / PrintWindow 截图 | — |
| pystray | >= 0.19 | 托盘 | — |
| ruff | >= 0.16 | Lint | ESLint |
| pytest | >= 8.0 | 测试 | JUnit |
| PyInstaller | >= 6.0 | 打包 | — |
| FastAPI / uvicorn / pydantic / SQLAlchemy | 已声明依赖 | 🎯 2.0 占位（`backend/server.py`、`backend/api/`、`frontend/`），未接入桌面端 | Spring Boot |

## 附录 C：新增功能 Checklist

```
┌─────────────────────────────────────────────────────────────────────┐
│  □ 1. 搜索现有实现（automation / features / contracts / repository） │
│  □ 2. 定位置：业务逻辑进 automation|domain|features；接口进 contracts │
│  □ 3. 遍历类功能：只写 SweepPolicy + 装配端口，不写循环              │
│  □ 4. 后台任务：业务 Worker + WorkerHost，结果信号用业务名            │
│  □ 5. Presenter：Property(带 notify) / Signal / Slot，文案在这里组装  │
│  □ 6. 在 registry.py 注册 Presenter；需要时用 OnWindowReady 注册回调  │
│  □ 7. QML：只绑定与转发，不拼字符串、不写判断                        │
│  □ 8. 新设置项先加进 SettingsManager._DEFAULTS                       │
│  □ 9. 异常只带消息；日志用 log；不要在 import 时做副作用             │
│  □ 10. 补测试（假端口优先）+ 加/更新架构守卫                          │
│  □ 11. ruff check + pytest 通过；更新本文与 docs/architecture.md      │
└─────────────────────────────────────────────────────────────────────┘
```

## 附录 D：🎯 待落地清单（写代码时别假设它们已存在）

| 项 | 目标 | 现状 |
|---|------|------|
| `backend/di/container.py` | 统一管理重量级资源生命周期，收编 `instance()` 单例 | 无容器，手工装配 |
| `backend/api_client/` | 统一 HTTP 层（超时/重试/代理/mock 友好） | 各处直接用 `requests` |
| `config/settings.yaml` + pydantic-settings | 部署期配置与用户设置分离 | 只有 `SettingsManager`（SQLite） |
| OCR Worker `moveToThread` | 槽函数自动在子线程执行 | 仍是继承 `QThread` 实现 |
| `WorkerHost` 排队能力 | 支持"任务完成回调里再起任务"的链式调用走托管 | 这类代码暂不托管 |
| `async_runner.py` | 统一的一次性任务接口 | 无人使用；新代码用 `WorkerHost` + 业务 Worker |
| 日志入库 | 界面内查询历史日志 | 只有状态栏桥接 |
| 测试分层 + `pytest-qt` + CI | 单元/集成分层、信号等待、自动跑 | 扁平测试 + 本地手动跑 |
| 调试面板 QML 文案下沉 | 去掉 `pages/debug_panels/*.qml` 里的字符串拼接 | 仅扫描面板改完（B 类清理） |
| 历史 BOM 清理 | 全仓 UTF-8 无 BOM | 约 47 个文件仍带 BOM |
| FastAPI + Vue 前端（2.0） | 桌面端之外的 Web 形态 | 占位文件保留，未接入 |

---
