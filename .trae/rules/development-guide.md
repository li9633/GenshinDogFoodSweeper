---
alwaysApply: true
---
# 项目开发规范

> **适用范围**：PySide6 >= 6.7 + Python 3.13 + PaddleOCR 3.0 + FastAPI + SQLite
> **版本**：v2.0（2026-08-11 更新）

---

## 0. 快速迁移指南：Vue3 + Spring Boot → PySide6


| Vue3 / Spring Boot 概念 | PySide6 对应物 | 本项目落地位置 | 关键差异 |
| :--- | :--- | :--- | :--- |
| `App.vue` / `main.ts` | `main.py` | `main.py` | 应用入口，负责创建 QApplication + 注册 Presenter |
| Vue SFC (`.vue`) | QML (`.qml`) | `ui/qml/pages/`, `ui/qml/components/` | QML 不支持 `<script setup>`，响应式靠 `Property + notify` |
| Pinia Store / Composables | Presenter (QObject) | `ui/presenters/` | 对标 Pinia，但必须用 `@Slot` 接收 UI 事件 |
| `ref` / `reactive` | `@Property(type, notify=signal)` | 各 Presenter 类 | Qt 的响应式是**显式通知**机制，不自动追踪 |
| `watch` / `computed` | `Signal` + 手动 `emit` | 各 Presenter 类 | 没有 `computed`，需要手动在 setter 里触发 |
| `@Emit` | `Signal.emit()` | 各 Presenter 类 | Qt 信号是类型安全的（定义时指定参数类型） |
| Axios / Fetch | `httpx` + `QThreadPool` | `api_client/`（待建） | **禁止**在 UI 线程直接 `requests.get()` |
| Spring `@Service` / `@Component` | 纯 Python 类（业务逻辑层） | `automation/`, `crawler/`, `utils/` | 不继承 QObject，不依赖 Qt |
| Spring `@Repository` / JPA | Repository 类 + SQLite | `database/repository/` | 使用 `get_db()` Context Manager，无 ORM |
| Spring `@Autowired` / IoC | `DependencyContainer` | `di/container.py`（待建） | 手动注入，无反射 |
| `@Async` / `@Scheduled` | `QThreadPool` / `QThread` | `automation/ocr_worker.py` | UI 线程不能阻塞，耗时操作必须异步 |
| Vue Router | `StackView` / `Loader` (QML) | `ui/qml/pages/` | QML 用 `StackView.push()` 切换页面 |
| `@Transactional` | `get_db()` Context Manager | `database/connection.py` | `with get_db() as db:` 自动 commit/rollback |
| Global Error Handler (Vue) | `sys.excepthook` + `qmlError` | `main.py` + `utils/logger.py` | Python 异常不捕获会导致**整个事件循环静默崩溃** |
| `.env` / `application.yml` | `config/settings.yaml` | `config/` | 用 `pydantic-settings` 或 `yaml` 读取 |
| ESLint / Prettier | `ruff` + `black` | `pyproject.toml` | Python 的 lint + format 工具链 |
| Vite HMR | `QML Hot Reload`（需 Qt 商业版） | — | 社区版无 HMR，改 QML 需重启应用 |

### 思维转换要点

1. **没有虚拟 DOM，没有 diff 算法** —— QML 的绑定是**直接赋值**，性能更好但更容易出 Bug
2. **没有浏览器事件循环** —— PySide6 的事件循环是 Qt 自己的，Python 的 `asyncio` **不会自动驱动**
3. **GIL 依然存在** —— Python 多线程是协作式的，CPU 密集型任务需要 `QProcess` 或多进程
4. **UI 线程 = 主线程** —— 任何超过 16ms 的同步操作都会让界面卡顿

---

## 1. 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    UI 层 (QML)                             │
│  仅负责渲染、用户交互、动画。不包含任何业务逻辑。           │
│  对标：Vue SFC 的 <template> + <style>                     │
├─────────────────────────────────────────────────────────────┤
│              Presenter 层 (QObject)                        │
│  桥接 UI 与业务逻辑。暴露 Property / Signal / Slot 供 QML   │
│  绑定。组装业务层返回的数据为 UI 可用的展示格式。           │
│  对标：Pinia Store + Composables                            │
├─────────────────────────────────────────────────────────────┤
│         业务逻辑层 (automation / crawler / api_client)     │
│  纯 Python 逻辑。OCR、模板匹配、截图、爬虫、HTTP 请求等。   │
│  不依赖任何 UI 框架，可独立测试。                           │
│  对标：Spring @Service + Axios 封装                         │
├─────────────────────────────────────────────────────────────┤
│        数据层 (models / database / config)                  │
│  实体对象 (Entity) + DTO + 仓库 (Repository) + 配置管理。   │
│  对标：JPA Entity + DTO + @Repository                       │
└─────────────────────────────────────────────────────────────┘
```

**核心原则：上层依赖下层，下层绝不依赖上层。**

**依赖方向**：
```
QML → Presenter → 业务逻辑层 → 数据层
                ↘ api_client → FastAPI/Spring Boot
```

---

## 2. 数据模型层（models/）

### 2.1 设计原则：对象思维

每个业务概念都对应一个明确的类，使用 `dataclass` 或普通类描述，**禁止使用裸 dict/list 在模块间传递数据**。

### 2.2 实体对象（Entity）

实体对应数据库中的一行记录，用于持久化场景。

```python
# 示例：圣遗物套装实体
class ArtifactSet:
    """圣遗物套装实体 — 对应 artifact_sets 表"""
    __slots__ = ("id", "name", "icon", "summary", "rarity", "set_effects")

    def __init__(self, id: int, name: str, ...):
        ...

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "ArtifactSet":
        """从数据库行构造实体"""
        ...

    def to_dict(self) -> dict:
        """转为字典（供序列化）"""
        ...
```

| 实体 | 对应表 | 文件 |
|------|--------|------|
| `ArtifactSet` | `artifact_sets` | `models/artifact_set.py` |
| `ArtifactPiece` | `artifact_pieces` | `models/artifact_piece.py` |

### 2.3 数据传输对象（DTO）

DTO 用于跨层传递数据，不绑定数据库结构。

```python
# 示例：识别结果 DTO
@dataclass
class ArtifactStat:
    """单个词条"""
    name: str
    value: float
    is_percentage: bool
    is_locked: bool = False

@dataclass
class ArtifactInfo:
    """圣遗物完整信息 — OCR 识别结果的结构化表示"""
    set_name: str | None = None
    piece_type: str | None = None
    rarity: int | None = None
    main_stat: ArtifactStat | None = None
    sub_stats: list[ArtifactStat] = field(default_factory=list)
    level: int | None = None
    is_locked: bool | None = None
```

**原则：**
- 实体（Entity）用于数据库映射
- DTO 用于业务逻辑间传递
- 不含任何 UI 相关字段（如颜色值、格式化字符串等）

---

## 3. UI 层与 Presenter 层分离（MVP 模式）

### 3.1 职责划分

| 层 | 可以做什么 | 不能做什么 |
|----|-----------|-----------|
| **QML (View)** | 渲染 UI、绑定属性、响应点击、动画 | 调用业务逻辑、直接操作数据库、处理数据 |
| **Presenter (QObject)** | 接收 UI 事件、调用业务层、组装展示数据、发射信号 | 创建 UI 组件、操作 DOM/Widget |

### 3.2 Presenter 规范

```python
class SomePresenter(QObject):
    """每个页面对应一个 Presenter，注册为 QML Context Property"""

    # ── 信号：状态变更时发射，驱动 QML 重新渲染 ──
    dataChanged = Signal()
    statusChanged = Signal(str)

    # ── 属性：暴露给 QML 绑定，必须有 notify 信号 ──
    @Property(str, notify=dataChanged)
    def displayText(self) -> str:
        return self._text

    # ── 槽：接收 QML 的用户操作 ──
    @Slot(str)
    def doSomething(self, param: str) -> None:
        result = business_layer.process(param)
        self._text = self._format_for_display(result)
        self.dataChanged.emit()  # ← 通知 UI 更新
```

### 3.3 数据流方向（单向）

```
用户操作 → QML 调用 Presenter Slot → Presenter 调用业务层
→ Presenter 更新内部状态 + emit 信号 → QML 属性绑定自动刷新 UI
```

**禁止：**
- QML 直接调用 `backend.automation.*` 或 `backend.database.*`
- QML 维护独立的业务状态（如 `ListModel` 手动增删）
- Presenter 中 import QML 类型或创建 UI 组件

### 3.4 展示数据的归属

展示格式化逻辑**属于 Presenter**，不属于 QML。

```python
# ✅ 正确：Presenter 提供展示就绪的数据
self._conditions.append({
    "key": key,
    "templateName": key,
    "fileName": self._template_file_map.get(key, key + ".png"),
    "thresholdText": f"{int(threshold * 100)}%",
    "regionText": "全屏" if not has_region else f"区域:({rx},{ry},{rw}x{rh})",
})
```

```qml
// ❌ 错误：QML 中拼接展示文本
text: modelData.key + "(" + getFileName(modelData.key) + ")"
```

---

## 4. 业务逻辑层（automation / crawler / api_client）

### 4.1 设计原则

- **纯 Python 代码**，不依赖 PySide6/Qt 的任何类型（特殊情况见 9.1）
- **可独立测试**，不依赖 UI 运行环境
- 使用类型注解，返回强类型对象（非 dict）
- **禁止**在业务逻辑中直接操作 QML 组件或访问 Presenter

### 4.2 模块划分

| 模块 | 职责 |
|------|------|
| `automation/recognizer.py` | 圣遗物识别：OCR 解析 + 套装匹配 + 星级检测 |
| `automation/template_matcher.py` | 多尺度模板匹配 |
| `automation/template_manager.py` | 模板文件管理（增删查） |
| `automation/ocr_engine.py` | OCR 引擎封装（PaddleOCR 初始化 + 推理） |
| `automation/ocr_worker.py` | OCR 专用线程 + 任务队列 |
| `crawler/` | 数据爬取（BBS 抓取、图标下载） |
| `utils/screen_capture.py` | 屏幕截图封装（win32 PrintWindow） |
| `api_client/` | FastAPI / Spring Boot 的 HTTP 调用封装 |

### 4.3 新增功能的标准流程（DRY 原则）

> **这是最容易出错的地方**：Python 桌面项目需要更谨慎地管理依赖。

**在编写任何新功能之前，必须执行以下检查：**

#### Step 1：查（Search）—— 搜索项目中是否已有同类实现

```bash
# 搜索现有的工具函数
grep -r "def screenshot" backend/utils/
grep -r "def match_template" backend/automation/
grep -r "class.*Repo" backend/database/
```

**检查清单：**

| 检查项 | 搜索位置 | 示例 |
|--------|---------|------|
| 通用工具函数 | `utils/` | 文件路径处理、图片编解码、日志封装 |
| 业务逻辑 | `automation/`, `crawler/` | OCR 识别、模板匹配、坐标计算 |
| 数据访问 | `database/repository/` | CRUD 操作、查询方法 |
| UI 组件 | `ui/qml/components/` | 通用按钮、对话框、表单 |
| 异步任务 | `automation/ocr_worker.py`, `utils/async_runner.py` | 线程池、任务队列 |
| 配置读取 | `config/` | 环境变量、模型路径、API 地址 |
| HTTP 请求 | `api_client/` | FastAPI 调用、第三方 API |
| 异常处理 | `utils/logger.py` | 错误捕获、重试逻辑 |

#### Step 2：引（Import）—— 如果已存在，直接复用

```python
# ✅ 正确：复用现有的截图工具
from utils.screen_capture import ScreenshotCapture

capturer = ScreenshotCapture()
image = capturer.capture_region(x, y, w, h)
```

```python
# ❌ 错误：复制粘贴了一份截图代码
import win32gui
import win32ui
# ... 50 行复制来的代码 ...
```

**复用原则：**
- **优先调用现有函数**，哪怕它的接口不是 100% 匹配你的需求
- 如果现有函数差一点，用**包装函数**或**继承**扩展它，而非复制
- 如果现有函数的接口设计不合理，**先重构它**，再在新功能中使用

#### Step 3：造（Create）—— 如果不存在，创建通用模块

新模块必须满足以下条件：

1. **单一职责**：一个文件只做一件事（如 `screen_capture.py` 只管截图）
2. **通用接口**：函数名和参数要通用化，不要绑定特定业务
3. **无 UI 依赖**：纯 Python，不 import PySide6（除非是 `automation/ocr_worker.py` 这类明确需要 Qt 的模块）
4. **可测试**：能在不启动 UI 的情况下单独运行

**命名规范：**

```python
# ❌ 错误：绑定了特定业务
def capture_for_artifact_recognition():
    ...

# ✅ 正确：通用命名
def capture_screen(region: tuple[int, int, int, int] | None = None) -> np.ndarray:
    ...

# ❌ 错误：函数名暴露了实现细节
def use_win32_to_get_window_handle():
    ...

# ✅ 正确：面向接口命名
def find_window_by_title(title: str) -> int:
    ...
```

#### Step 4：注入（Inject）—— 通过构造函数传入依赖

```python
# ❌ 错误：在 Presenter 内部硬编码创建依赖
class ArtifactPresenter(QObject):
    def __init__(self):
        super().__init__()
        self._recognizer = ArtifactRecognizer()  # 硬编码
        self._capturer = ScreenshotCapture()     # 硬编码

# ✅ 正确：通过构造函数注入（对标 Spring @Autowired）
class ArtifactPresenter(QObject):
    def __init__(
        self,
        recognizer: ArtifactRecognizer,
        capturer: ScreenshotCapture,
        ocr_worker: OcrWorker,
    ):
        super().__init__()
        self._recognizer = recognizer
        self._capturer = capturer
        self._ocr_worker = ocr_worker
```

#### Step 5：注册（Register）—— 在 DependencyContainer 中统一管理

详见第 8 节。

#### Step 6：测试（Test）—— 编写单元测试

```python
# tests/test_screen_capture.py
from utils.screen_capture import ScreenshotCapture

def test_capture_full_screen():
    capturer = ScreenshotCapture()
    img = capturer.capture_screen()
    assert img is not None
    assert img.shape[2] == 3  # RGB
```

#### Step 7：文档（Document）—— 更新本文档

在对应的章节中添加新模块说明。

### 4.4 Code Review 检查清单

提交 PR 前，自查以下条目：

- [ ] 是否搜索过现有代码，确认没有重复实现？
- [ ] 新函数是否放在了正确的模块目录中？
- [ ] 是否通过构造函数注入依赖，而非硬编码 `import`？
- [ ] 是否在 `DependencyContainer` 中注册了新服务？
- [ ] 是否有对应的单元测试？
- [ ] 耗时操作是否异步化（不在 UI 线程执行）？
- [ ] 是否使用了类型注解？
- [ ] 是否使用了 `log` 而非 `print()`？
- [ ] 数据库操作是否通过 `get_db()` Context Manager？
- [ ] QML 中是否没有业务逻辑？

---

## 5. 数据层（database/）

### 5.1 Repository 模式

每个表对应一个 Repository 类，封装所有 CRUD 操作。

```python
class ArtifactSetRepo:
    """artifact_sets 表数据访问"""

    @classmethod
    def create_table(cls) -> None: ...

    @classmethod
    def find_all(cls) -> list[ArtifactSet]: ...

    @classmethod
    def find_by_id(cls, set_id: int) -> ArtifactSet | None: ...

    @classmethod
    def upsert(cls, entity: ArtifactSet) -> None: ...
```

**原则：**
- Repository 只返回实体对象，不返回裸 dict / tuple
- 调用方不需要知道 SQL 细节
- 数据库连接通过 `get_db()` 统一管理

### 5.2 数据库连接管理

**配置：** SQLite（artifacts.db + app.db），开启 WAL 模式 + 外键约束，使用 `contextmanager` 模式的 `get_db()`。

```python
# database/connection.py
import sqlite3
from contextlib import contextmanager

@contextmanager
def get_db(db_path: str = "artifacts.db"):
    """获取数据库连接的 Context Manager"""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**正确用法：**

```python
def save_artifact(artifact: ArtifactInfo) -> None:
    with get_db() as db:
        db.execute(
            "INSERT INTO artifacts (set_name, rarity) VALUES (?, ?)",
            (artifact.set_name, artifact.rarity)
        )
    # 连接在此处自动关闭
```

**错误用法：**

```python
# ❌ 禁止：手动管理连接，容易泄漏
db = get_db().__enter__()
db.execute("INSERT ...")
# 忘记 commit / close → 连接泄漏 → 数据库锁

# ❌ 禁止：跨线程传递连接
def worker_thread(db):
    db.execute("SELECT ...")  # SQLite 连接不能跨线程使用
```

### 5.3 SQLite 并发注意事项

| 场景 | 风险 | 解决方案 |
|------|------|---------|
| UI 线程 + 爬虫线程同时写库 | `OperationalError: database is locked` | 使用 WAL 模式（已配置）+ 短事务 |
| 长事务持有连接 | 阻塞其他线程 | 事务尽量短，批量操作分批提交 |
| 跨线程传递连接对象 | 未定义行为 | 每个线程独立 `get_db()` |

---

## 6. 文件组织规范

```
backend/
├── di/                          # 依赖注入容器（新增）
│   └── container.py             # DependencyContainer
├── config/                      # 配置文件（新增）
│   └── settings.yaml            # 环境配置
├── models/                      # 数据模型（Entity + DTO）
│   ├── artifact.py              # ArtifactInfo, ArtifactStat (DTO)
│   ├── artifact_set.py          # ArtifactSet (Entity)
│   └── artifact_piece.py        # ArtifactPiece (Entity)
├── database/
│   ├── connection.py            # get_db() Context Manager
│   └── repository/              # 数据访问层（Repository）
│       ├── artifact_set_repo.py
│       └── artifact_piece_repo.py
├── automation/                  # 业务逻辑层
│   ├── recognizer.py
│   ├── template_matcher.py
│   ├── template_manager.py
│   ├── ocr_engine.py            # PaddleOCR 引擎封装
│   ├── ocr_worker.py            # OCR 专用线程 + 任务队列
│   └── async_runner.py         # 通用一次性异步任务
├── crawler/                     # 爬虫层
├── api_client/                  # HTTP 调用封装（新增）
│   └── base_client.py
├── ui/
│   ├── presenters/              # Presenter 层（QObject）
│   │   ├── settings_presenter.py
│   │   ├── artifact_recognition_presenter.py
│   │   └── ...
│   └── qml/                     # UI 层（QML）
│       ├── pages/
│       │   ├── SettingsPage.qml
│       │   └── debug_panels/
│       └── components/
├── utils/                       # 通用工具
│   ├── screen_capture.py
│   ├── logger.py                # loguru 配置
│   └── log_bridge.py            # 日志 → DB + 状态栏桥接
└── main.py                      # 应用入口 + 容器初始化
```

---

## 7. 命名与编码规范

### 7.1 Python

- 类名：`PascalCase`（如 `ArtifactRecognizer`）
- 方法/函数：`snake_case`（如 `add_condition`）
- 私有成员：前缀 `_`（如 `self._conditions`）
- 信号：过去式动词（如 `dataChanged`、`syncFinished`）
- 槽：动词短语（如 `startSync`、`removeCondition`）
- 类型注解：所有公开方法必须有完整的参数和返回值类型注解
- Python 版本：>= 3.13.7（使用 `list[int]` 而非 `List[int]`，`str | None` 而非 `Optional[str]`）

### 7.2 QML

- 文件名：`PascalCase`（如 `SettingsPage.qml`）
- 属性：`camelCase`（如 `selectionMode`）
- 信号处理函数：`on` + 信号名（如 `onRecognitionFinished`）
- id：`camelCase`（如 `templateCombo`）
- 绑定 Presenter 属性时，优先使用直接绑定而非手动赋值
- **禁止**在 QML 中写业务逻辑（计算、条件判断应放在 Presenter）
- **禁止**在 QML 中使用 `console.log` 打印业务日志（仅允许调试 UI 布局）

### 7.3 禁止事项

- 禁止在 QML 中写业务逻辑
- 禁止在 Presenter 中 import QML 类型
- 禁止跨层直接访问数据库
- 禁止使用裸 `dict`/`list` 在模块间传递业务数据
- 禁止 `@Property` 缺少 `notify` 信号
- 禁止使用 `print()` 替代 `log`（见 10.3）
- 禁止在 UI 线程执行耗时操作（见 9.2）

### 7.4 复用原则与 DRY（Don't Repeat Yourself）

**核心规则：在新增任何功能之前，必须先搜索项目中是否已有同类实现。**

#### 7.4.1 「查-引-造」三步流程

```
┌─────────────────────────────────────────────────────────┐
│  Step 1: 查 (Search)                                   │
│  搜索现有代码库，确认是否已有类似功能                     │
├─────────────────────────────────────────────────────────┤
│  Step 2: 引 (Import)                                   │
│  如果已存在 → 直接复用，通过依赖注入传入                  │
│  如果接口不匹配 → 扩展现有类，而非复制一份                 │
├─────────────────────────────────────────────────────────┤
│  Step 3: 造 (Create)                                   │
│  如果不存在 → 创建新模块                                 │
│  新模块必须：单一职责 + 通用接口 + 无 UI 依赖 + 可测试    │
└─────────────────────────────────────────────────────────┘
```

#### 7.4.2 复用检查清单

在编写新代码前，逐一确认：

| # | 检查项 | 搜索方式 |
|---|--------|---------|
| 1 | 是否有现成的工具函数？ | 检查 `utils/` 目录 |
| 2 | 是否有现成的业务逻辑类？ | 检查 `automation/`, `crawler/` |
| 3 | 是否有现成的 Repository？ | 检查 `database/repository/` |
| 4 | 是否有现成的 QML 组件？ | 检查 `ui/qml/components/` |
| 5 | 是否有现成的异步任务封装？ | 检查 `ocr_worker.py`, `async_runner.py` |
| 6 | 是否有现成的配置项？ | 检查 `config/settings.yaml` |

#### 7.4.3 反模式示例

```python
# ❌ 反模式 1：复制粘贴
# 在 file_a.py 中
def resize_image(img, w, h):
    return cv2.resize(img, (w, h))

# 在 file_b.py 中又写了一遍
def resize_image(img, width, height):  # 参数名还不一样
    return cv2.resize(img, (width, height))

# ✅ 正确：抽到 utils/image_utils.py，两处都 import
```

```python
# ❌ 反模式 2：绕开现有架构
# 直接在 QML 的 JavaScript 里写业务判断
function checkArtifactQuality(stats) {
    let total = 0
    for (let i = 0; i < stats.length; i++) {
        total += stats[i].value
    }
    return total > 100
}

# ✅ 正确：在 Presenter 中计算，QML 只负责显示
# Presenter:
@property(bool, notify=dataChanged)
def isHighQuality(self) -> bool:
    return sum(s.value for s in self._artifact.sub_stats) > 100
```

### 7.5 依赖注入与解耦（IoC 容器）

> **对标 Spring Boot 的 `@Autowired` + `@Component`**

#### 7.5.1 当前问题

项目目前存在多种单例实现（`OcrWorker.instance()`、`PreviewImageProvider._instance`、`OcrEngine._ocr`），且 Presenter 在 `main.py` 中手动 `new` + 手动 `setContextProperty`。这导致：
- 依赖关系隐式化（看不出 Presenter A 依赖 B）
- 无法统一管理生命周期
- 难以 Mock 测试

#### 7.5.2 DependencyContainer 规范

**创建容器：**

```python
# backend/di/container.py
from automation.ocr_worker import OcrWorker
from utils.logger import log
from utils.log_bridge import LogBridge

class DependencyContainer:
    """对标 Spring 的 ApplicationContext"""

    def __init__(self):
        self._ocr_worker: OcrWorker | None = None
        self._log_bridge: LogBridge | None = None
        self._initialized = False

    def init_resources(self):
        """初始化所有重量级资源（仅一次，在 main.py 中调用）"""
        if self._initialized:
            return

        # OCR 引擎（启动专用线程 + 加载 PaddleOCR 模型）
        self._ocr_worker = OcrWorker()
        self._ocr_worker.start()

        # 日志桥接
        self._log_bridge = LogBridge()

        self._initialized = True

    def shutdown(self):
        """优雅关闭所有资源"""
        if self._ocr_worker:
            self._ocr_worker.stop()
            self._ocr_worker.wait()
        self._initialized = False

    # ── 资源访问器 ──
    def get_ocr_worker(self) -> OcrWorker:
        if not self._ocr_worker:
            raise RuntimeError("DependencyContainer not initialized")
        return self._ocr_worker

    def get_log_bridge(self) -> LogBridge:
        return self._log_bridge

# 全局唯一容器实例（对标 Spring 的 ApplicationContext）
container = DependencyContainer()
```

**在 main.py 中使用：**

```python
# main.py
import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from di.container import container
from ui.presenters.settings_presenter import SettingsPresenter
from ui.presenters.artifact_recognition_presenter import ArtifactRecognitionPresenter

def main():
    app = QGuiApplication(sys.argv)

    # 1. 初始化所有重量级资源
    container.init_resources()

    # 2. 创建 Presenter（依赖通过构造函数注入）
    settings_presenter = SettingsPresenter(
        config_path="config/settings.yaml"
    )

    artifact_presenter = ArtifactRecognitionPresenter(
        ocr_worker=container.get_ocr_worker()
    )

    # 3. 注册到 QML
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("SettingsPresenter", settings_presenter)
    engine.rootContext().setContextProperty("ArtifactRecognition", artifact_presenter)

    # 4. 加载主 QML
    engine.load("ui/qml/main.qml")

    # 5. 优雅退出
    app.aboutToQuit.connect(container.shutdown)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

#### 7.5.3 单例收编计划

| 现有单例 | 当前实现 | 迁移目标 |
|---------|---------|---------|
| `OcrWorker.instance()` | `@classmethod instance()` + `_instance` 类变量 | 改为普通类，由 `DependencyContainer` 管理生命周期 |
| `PreviewImageProvider._instance` | `_instance` 类变量 + `@staticmethod put()` | 改为由容器创建，注入到需要的 Presenter |
| `OcrEngine._ocr` | `_ocr` 类变量，所有实例共享 | 改为 `OcrWorker` 内部持有，外部不直接访问 |

**迁移原则：**
- 不删除现有接口（保持向后兼容）
- 新代码必须使用 `DependencyContainer`
- 逐步废弃旧的 `instance()` 方法

---

## 8. 异步与线程安全规范

> **PySide6 的 UI 线程是**单线程事件循环**。任何超过 16ms 的同步操作都会让界面卡顿。

### 8.1 PaddleOCR 线程独占原则（强制）

**问题背景：** PaddleOCR 3.0 底层为 C++ 实现，引擎实例**只能在创建它的线程中使用**。这是 PaddlePaddle 框架的线程亲和性限制。

**解决方案：** 为 PaddleOCR 创建**专用 QThread**，引擎在该线程中初始化并常驻，所有识别任务通过信号槽提交到该线程排队执行。

#### 推荐架构（Worker Object + moveToThread 模式）

> **注意：** 项目当前的 `OcrWorker` 是**继承 QThread** 的实现。Qt 官方推荐**继承 QObject + moveToThread** 的模式，更灵活且不易出错。建议逐步迁移。

**架构图：**

```
┌─────────────┐     Signal(submit)       ┌──────────────────────────┐
│  Presenter  │ ──────────────────────> │   OcrWorker (QObject)     │
│  (UI Thread)│                          │   (OCR Dedicated Thread)  │
└─────────────┘ <────────────────────── └──────────────────────────┘
      │              Signal(resultReady)            │
      │                                             ├──> self._ocr.ocr()
      │                                             └──> PaddleOCR 引擎实例
      │                                                  (仅在此线程初始化)
      │
┌─────▼─────┐
│   QML     │
│  (更新UI) │
└───────────┘
```

**实现代码：**

```python
# backend/automation/ocr_worker.py
from PySide6.QtCore import QObject, Signal, Slot, QThread
from queue import Queue
import traceback

class OcrWorker(QObject):
    """
    PaddleOCR 专用 Worker。
    必须 moveToThread 到专用 QThread 中使用。
    """

    # ── 信号 ──
    resultReady = Signal(object, str)   # (result, callback_data)
    errorOccurred = Signal(str, str)    # (error_msg, callback_data)
    initialized = Signal()              # OCR 引擎初始化完成

    def __init__(self):
        super().__init__()
        self._ocr = None
        self._task_queue: Queue = Queue()
        self._initialized = False

    @Slot()
    def initialize(self):
        """在子线程中初始化 PaddleOCR 引擎"""
        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                det_model_dir="engines/official_models/PP-OCRv5_mobile_det",
                rec_model_dir="engines/official_models/PP-OCRv5_mobile_rec",
                use_angle_cls=True,
                show_log=False,
            )
            self._initialized = True
            self.initialized.emit()
            log.info("PaddleOCR 引擎初始化完成")
        except Exception as e:
            log.error(f"PaddleOCR 初始化失败: {e}")
            self.errorOccurred.emit(str(e), "")

    @Slot(str, str)
    def process_image(self, image_path: str, callback_data: str = ""):
        """执行 OCR 识别（运行在子线程）"""
        if not self._initialized or not self._ocr:
            self.errorOccurred.emit("OCR Engine not initialized", callback_data)
            return
        try:
            result = self._ocr.ocr(image_path, cls=True)
            self.resultReady.emit(result, callback_data)
        except Exception as e:
            log.error(f"OCR 识别失败: {traceback.format_exc()}")
            self.errorOccurred.emit(str(e), callback_data)

    def submit(self, image_path: str, callback_data: str = ""):
        """
        供外部调用的便捷方法。
        通过信号跨线程提交任务（线程安全）。
        """
        self.process_image.emit(image_path, callback_data)
```

**在 DependencyContainer 中初始化：**

```python
# backend/di/container.py
from PySide6.QtCore import QThread

class DependencyContainer:
    def __init__(self):
        self._ocr_thread: QThread | None = None
        self._ocr_worker: OcrWorker | None = None

    def init_resources(self):
        if self._initialized:
            return

        # 创建专用线程
        self._ocr_thread = QThread()
        self._ocr_thread.setObjectName("OCR-Thread")

        # 创建 Worker
        self._ocr_worker = OcrWorker()

        # 将 Worker 移动到专用线程
        self._ocr_worker.moveToThread(self._ocr_thread)

        # 连接信号：线程启动时初始化 OCR 引擎
        self._ocr_thread.started.connect(self._ocr_worker.initialize)

        # 启动线程（进入事件循环，等待任务）
        self._ocr_thread.start()

        self._initialized = True

    def shutdown(self):
        if self._ocr_thread:
            self._ocr_thread.quit()
            self._ocr_thread.wait(5000)  # 最多等 5 秒
        self._initialized = False
```

**在 Presenter 中调用：**

```python
# backend/ui/presenters/artifact_recognition_presenter.py
from PySide6.QtCore import QObject, Signal, Slot, QObject

class ArtifactRecognitionPresenter(QObject):
    statusChanged = Signal(str)
    recognitionFinished = Signal(object)

    def __init__(self, ocr_worker: OcrWorker):
        super().__init__()
        self._ocr_worker = ocr_worker

        # 连接 Worker 的信号到 Presenter 的槽
        self._ocr_worker.resultReady.connect(self._on_ocr_finished)
        self._ocr_worker.errorOccurred.connect(self._on_ocr_error)

    @Slot(str)
    def startRecognition(self, image_path: str):
        """用户点击识别按钮 → 提交到 OCR 线程"""
        self.statusChanged.emit("识别中...")
        # 通过信号提交任务（线程安全，不会阻塞 UI）
        self._ocr_worker.submit(image_path, callback_data="artifact_001")

    @Slot(object, str)
    def _on_ocr_finished(self, result: list, callback_data: str):
        """识别完成（此函数在 UI 线程执行）"""
        self.statusChanged.emit("识别完成")
        self.recognitionFinished.emit(result)

    @Slot(str, str)
    def _on_ocr_error(self, error_msg: str, callback_data: str):
        self.statusChanged.emit(f"识别失败: {error_msg}")
        log.error(f"OCR 错误 [{callback_data}]: {error_msg}")
```

#### 为什么不用 `QThread.run()` 里写 while 循环？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **继承 QThread + while 循环**（当前方案） | 简单直接 | `run()` 外的槽函数运行在 UI 线程；难以扩展 |
| **QObject + moveToThread**（推荐） | 所有槽函数自动在子线程执行；灵活组合多个 Worker | 需要多写几行胶水代码 |

### 8.2 耗时操作异步化清单

以下操作**严禁**在 UI 线程同步执行：

| 操作 | 耗时级别 | 推荐方案 | 当前状态 |
|------|---------|---------|---------|
| PaddleOCR 推理 | 1-3 秒 | 专用 QThread + 任务队列 (OcrWorker) | ✅ 符合 |
| 多尺度模板匹配 | 100-500ms | `QThreadPool` + `QRunnable` | ❌ 需改造 |
| 截图 (PrintWindow) | 50-200ms | `AsyncRunner`（一次性任务） | ⚠️ 已存在，需规范 |
| 爬虫请求 | 数秒 | `QThreadPool` + `QRunnable` | ❌ 需改造 |
| FastAPI 调用 | 数百ms-数秒 | `httpx.AsyncClient` + `QThreadPool` | ❌ 待建 |

### 8.3 统一异步接口

项目目前存在两套异步机制（`OcrWorker` 常驻线程 + `AsyncRunner` 一次性线程）。**新增代码**应遵循以下原则：

#### 原则 1：常驻任务用专用 QThread

适合：OCR 引擎、日志监控、实时数据采集等**需要保持状态**的任务。

#### 原则 2：一次性任务用 QThreadPool

适合：截图、文件读写、单次 HTTP 请求、模板匹配等**无状态**的任务。

```python
# backend/utils/async_runner.py (已有，规范化)
from PySide6.QtCore import QRunnable, QThreadPool, QObject, Signal

class TaskRunner(QRunnable):
    """通用一次性异步任务"""
    def __init__(self, fn, on_result=None, on_error=None):
        super().__init__()
        self._fn = fn
        self._on_result = on_result
        self._on_error = on_error

    def run(self):
        try:
            result = self._fn()
            if self._on_result:
                # 注意：QRunnable 不能直接 emit Signal
                # 需要通过 QMetaObject.invokeMethod 回到 UI 线程
                self._on_result(result)
        except Exception as e:
            if self._on_error:
                self._on_error(e)

def run_async(fn, on_result=None, on_error=None, parent=None):
    """便捷函数：提交一次性异步任务到全局线程池"""
    task = TaskRunner(fn, on_result, on_error)
    QThreadPool.globalInstance().start(task)
```

**使用示例：**

```python
# Presenter 中
@Slot()
def captureAndMatch(self):
    """截图 + 模板匹配（异步执行，不阻塞 UI）"""
    self.statusChanged.emit("截图中...")

    def do_work():
        # 在后台线程执行
        img = self._capturer.capture_screen()
        result = multi_scale_match(img, self._templates)
        return result

    def on_result(result):
        # 回到 UI 线程
        self._match_result = result
        self.dataChanged.emit()

    def on_error(e):
        log.error(f"截图匹配失败: {e}")
        self.statusChanged.emit("操作失败")

    run_async(do_work, on_result=on_result, on_error=on_error)
```

### 8.4 异步化改造优先级

| 优先级 | 任务 | 原因 |
|--------|------|------|
| 🔴 P0 | 多尺度模板匹配异步化 | 500ms 阻塞 = 肉眼可见的卡顿 |
| 🔴 P0 | 爬虫请求异步化 | 数秒阻塞 = 应用假死 |
| 🟡 P1 | OcrWorker 迁移到 moveToThread | 当前可用但有隐患 |
| 🟡 P1 | FastAPI 调用封装到 api_client/ | 统一 HTTP 调用层 |
| 🟢 P2 | 截图操作异步化 | 200ms 偶尔卡一下，体验尚可 |

---

## 9. 网络与通信规范

### 9.1 API Client 封装层

> **对标 Axios 封装**：Vue 项目中会创建一个 `api/` 目录统一管 HTTP 调用，PySide6 项目也一样。

**禁止**在 Presenter 中直接使用 `requests` 或 `httpx`。**必须**通过 `api_client/` 层封装。

```python
# backend/api_client/base_client.py
import httpx
from PySide6.QtCore import QObject, Signal, Slot, QThreadPool, QRunnable

class ApiClient(QObject):
    """HTTP API 客户端基类"""

    responseReceived = Signal(dict, str)  # (data, request_id)
    requestFailed = Signal(str, str)      # (error_msg, request_id)

    def __init__(self, base_url: str, timeout: float = 10.0):
        super().__init__()
        self._base_url = base_url
        self._timeout = timeout
        self._client = httpx.Client(base_url=base_url, timeout=timeout)

    def get(self, path: str, params: dict | None = None) -> dict:
        """同步 GET 请求（仅在后台线程调用）"""
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: dict | None = None) -> dict:
        """同步 POST 请求（仅在后台线程调用）"""
        resp = self._client.post(path, json=json)
        resp.raise_for_status()
        return resp.json()

    def close(self):
        self._client.close()
```

**在 Presenter 中异步调用：**

```python
# Presenter 中
@Slot(str)
def fetchArtifactDetail(self, artifact_id: str):
    """从 FastAPI/Spring Boot 获取圣遗物详情"""
    self.statusChanged.emit("加载中...")

    def do_request():
        # 在后台线程执行 HTTP 请求
        return self._api_client.get(f"/artifacts/{artifact_id}")

    def on_result(data: dict):
        self._artifact_detail = ArtifactInfo(**data)
        self.statusChanged.emit("加载完成")
        self.dataChanged.emit()

    def on_error(e: Exception):
        log.error(f"API 请求失败: {e}")
        self.statusChanged.emit("加载失败")

    run_async(do_request, on_result=on_result, on_error=on_error)
```

### 9.2 环境配置管理

> **对标 Vue 的 `.env.development` / `.env.production`**

```yaml
# config/settings.yaml
app:
  name: "Artifact Recognition Tool"
  version: "2.0.0"
  debug: true

paths:
  engines: "engines/official_models/"
  databases:
    artifacts: "data/artifacts.db"
    app: "data/app.db"
  logs: "logs/"

ocr:
  det_model: "PP-OCRv5_mobile_det"
  rec_model: "PP-OCRv5_mobile_rec"
  use_angle_cls: true
  lang: "ch"

api:
  fastapi_base_url: "http://localhost:8000"
  spring_boot_base_url: "http://localhost:8080"
  timeout: 10

ui:
  qt_style: "Basic"
  qml_import_path: "ui/qml"
```

**读取配置：**

```python
# backend/config/settings.py
import yaml
from pathlib import Path

class Settings:
    """配置管理（对标 pydantic-settings）"""
    def __init__(self, config_path: str = "config/settings.yaml"):
        self._config = self._load(config_path)

    def _load(self, path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    @property
    def ocr_det_model(self) -> str:
        return self._config["ocr"]["det_model"]

    @property
    def fastapi_base_url(self) -> str:
        return self._config["api"]["fastapi_base_url"]

    @property
    def debug(self) -> bool:
        return self._config["app"].get("debug", False)

# 全局配置实例
settings = Settings()
```

### 9.3 线程安全与 GIL 注意事项

| 场景 | Python GIL 影响 | 建议方案 |
|------|----------------|---------|
| PaddleOCR 推理（C++ 底层） | C++ 代码会释放 GIL，真正并行 | 专用线程即可 |
| OpenCV 图像处理 | 大部分 C++ 实现，释放 GIL | 可多线程并行 |
| 纯 Python 循环（如多尺度匹配） | 受 GIL 限制，不真正并行 | 用 `QThread` 避免阻塞 UI，但别指望多核加速 |
| CPU 密集型纯 Python | GIL 瓶颈 | 考虑 `multiprocessing` 或 `QProcess` |

---

## 10. 全局异常与日志规范

### 10.1 全局异常屏障（强制）

> **Python 3.13 对未处理异常更加严格**。Slot 回调中抛出的未捕获异常会导致**Qt 事件循环静默崩溃**（程序无响应但不退出，无错误提示）。

**在 `main.py` 入口设置全局异常钩子：**

```python
# main.py
import sys
import traceback
from utils.logger import log

def global_exception_hook(exctype, value, tb):
    """捕获所有未处理的 Python 异常"""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    log.critical(f"未捕获的全局异常:\n{error_msg}")
    # 调用原始钩子（确保异常信息输出到 stderr）
    sys.__excepthook__(exctype, value, tb)
    # 可选：弹出错误对话框后优雅退出
    # QMessageBox.critical(None, "致命错误", f"程序遇到未处理的异常:\n{value}")
    # QApplication.quit()

sys.excepthook = global_exception_hook
```

**捕获 QML 引擎错误：**

```python
# main.py
engine = QQmlApplicationEngine()

def on_qml_error(errors):
    for error in errors:
        log.error(f"QML Error: {error.toString()} at {error.url()}:{error.line()}")

engine.errorsChanged.connect(on_qml_error)
```

### 10.2 Slot 异常防护

**所有 `@Slot` 装饰的槽函数必须包含 try-except**：

```python
# ❌ 错误：未捕获异常 → UI 线程崩溃 → 应用假死
@Slot(str)
def on_button_clicked(self, text: str):
    self.do_something(text)  # 如果抛出异常，整个事件循环停止

# ✅ 正确：捕获异常 + 日志记录 + 用户反馈
@Slot(str)
def on_button_clicked(self, text: str):
    try:
        self.do_something(text)
    except ValueError as e:
        log.warning(f"参数错误: {e}")
        self.statusChanged.emit(f"输入有误: {e}")
    except Exception as e:
        log.error(f"Slot 执行失败: {traceback.format_exc()}")
        self.statusChanged.emit("操作失败，请查看日志")
```

### 10.3 日志规范

**统一使用 loguru，禁止混用 `print()` 和 `logging`：**

```python
# ✅ 正确
from utils.logger import log

log.info("识别完成，耗时 {:.2f}s", elapsed)
log.warning("模板匹配置信度过低: {}", score)
log.error("数据库连接失败: {}", e)
log.debug("OCR 原始结果: {}", result)
```

```python
# ❌ 错误
print("debug info")  # 不会被记录到文件
import logging
logging.info("xxx")   # 与 loguru 冲突，格式不统一
```

**日志级别使用规范：**

| 级别 | 使用场景 | 示例 |
|------|---------|------|
| `TRACE` | 极详细的调试信息（生产环境关闭） | 每次像素级操作、循环迭代 |
| `DEBUG` | 开发调试信息 | 函数入参、中间结果 |
| `INFO` | 正常业务流程 | "OCR 引擎初始化完成"、"用户点击识别按钮" |
| `WARNING` | 不影响功能但需注意 | "模板匹配置信度低于阈值"、"配置项缺失，使用默认值" |
| `ERROR` | 功能失败但不影响程序运行 | "截图失败"、"API 请求超时" |
| `CRITICAL` | 致命错误，可能导致崩溃 | "PaddleOCR 初始化失败"、"数据库损坏" |

**日志输出目标：**

| Sink | 级别 | 用途 |
|------|------|------|
| 控制台（彩色） | DEBUG | 开发时实时查看 |
| 文件（按天轮转，10MB/7天） | INFO | 持久化记录 |
| 错误文件（ERROR 级别） | ERROR | 快速定位问题 |
| 数据库（LogRepo.insert） | INFO | 程序内查询历史日志 |
| 状态栏回调 | WARNING+ | 实时通知用户 |

---

## 11. 配置与环境管理

### 11.1 环境变量

| 变量 | 用途 | 默认值 |
|------|------|-------|
| `QT_QUICK_CONTROLS_STYLE` | 强制 QML 控件样式 | `Basic`（强制，以支持自定义样式） |
| `PYTHONPATH` | Python 模块搜索路径 | 项目根目录 |
| `LOG_LEVEL` | 日志级别 | `INFO`（开发时设为 `DEBUG`） |
| `APP_ENV` | 运行环境 | `development` / `production` |

### 11.2 依赖管理

**使用 `pyproject.toml` 管理依赖（PEP 621）：**

```toml
# pyproject.toml
[project]
name = "artifact-recognition-tool"
version = "2.0.0"
requires-python = ">=3.13.7"

dependencies = [
    "PySide6>=6.7",
    "paddlepaddle>=3.0.0,<3.1.0",
    "paddleocr>=3.0.0",
    "opencv-python-headless>=4.10",
    "loguru>=0.7",
    "httpx>=0.27",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.6",
    "black>=24.0",
    "mypy>=1.10",
]
```

### 11.3 代码质量工具

| 工具 | 用途 | 配置文件 |
|------|------|---------|
| `ruff` | Lint（替代 flake8 + pylint） | `pyproject.toml` |
| `black` | 格式化（强制统一风格） | `pyproject.toml` |
| `mypy` | 静态类型检查 | `pyproject.toml` |
| `pytest` | 单元测试 | `pytest.ini` |

**推荐配置：**

```toml
# pyproject.toml 中的工具配置
[tool.ruff]
line-length = 100
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM"]
ignore = ["E501"]  # 行长度由 black 管理

[tool.black]
line-length = 100
target-version = ["py313"]

[tool.mypy]
python_version = "3.13"
strict = true
```

---

## 12. 测试规范

### 12.1 测试目录结构

```
tests/
├── conftest.py              # pytest 夹具（fixtures）
├── unit/
│   ├── test_ocr_engine.py
│   ├── test_template_matcher.py
│   └── test_repository.py
├── integration/
│   ├── test_recognition_flow.py
│   └── test_api_client.py
└── fixtures/
    ├── sample_screenshot.png
    └── test_settings.yaml
```

### 12.2 单元测试示例

```python
# tests/unit/test_ocr_engine.py
import pytest
from unittest.mock import MagicMock, patch
from automation.ocr_worker import OcrWorker

@pytest.fixture
def ocr_worker(qtbot):
    """创建 OcrWorker 实例（不启动真实 OCR 引擎）"""
    worker = OcrWorker()
    yield worker

def test_worker_initial_state(ocr_worker):
    assert ocr_worker._initialized is False
    assert ocr_worker._ocr is None

@patch("automation.ocr_worker.PaddleOCR")
def test_initialize(mock_paddle, ocr_worker, qtbot):
    """测试 OCR 引擎初始化"""
    mock_paddle.return_value = MagicMock()

    with qtbot.waitSignal(ocr_worker.initialized, timeout=5000):
        ocr_worker.initialize()

    assert ocr_worker._initialized is True
    mock_paddle.assert_called_once()

def test_process_image_without_init(ocr_worker, qtbot):
    """未初始化时调用 process_image 应发射 errorOccurred"""
    with qtbot.waitSignal(ocr_worker.errorOccurred, timeout=1000):
        ocr_worker.process_image("fake_path.png", "test_callback")
```

### 12.3 集成测试示例

```python
# tests/integration/test_recognition_flow.py
import pytest
from di.container import DependencyContainer

@pytest.fixture(scope="module")
def container():
    """启动真实（或 Mock）的依赖容器"""
    c = DependencyContainer()
    c.init_resources()
    yield c
    c.shutdown()

def test_full_recognition_flow(container, qtbot, tmp_path):
    """完整流程：截图 → OCR → 解析 → 存储"""
    worker = container.get_ocr_worker()

    test_image = tmp_path / "test_screenshot.png"
    test_image.write_bytes(b"fake_image_data")  # 替换为真实测试图片

    results = []
    with qtbot.waitSignal(worker.resultReady, timeout=10000):
        worker.submit(str(test_image), "integration_test")

    assert len(results) > 0
```

---

## 13. 性能优化指南

### 13.1 已识别的性能瓶颈与解决方案

| 瓶颈 | 当前耗时 | 优化方案 | 预期效果 |
|------|---------|---------|---------|
| PaddleOCR 冷启动 | 3-5 秒（首次加载模型） | 应用启动时预加载 + 引擎常驻 | 用户无感知 |
| 多尺度模板匹配 | 100-500ms | 异步化 + 减少缩放级别（10→5） | UI 零卡顿 |
| 截图 (PrintWindow) | 50-200ms | 异步化 + 区域截图优化 | 消除卡顿 |
| QML 列表渲染 | 卡顿（>100 项） | `ListView` + `delegate` 懒加载 | 流畅滚动 |
| 数据库写入 | 偶尔锁库 | WAL 模式（已配）+ 批量事务 | 无锁等待 |

### 13.2 QML 性能最佳实践

```qml
// ✅ 正确：使用 ListView 懒加载（仅渲染可见项）
ListView {
    model: artifactModel
    delegate: ArtifactItem {
        // delegate 只在可见时创建
    }
    cacheBuffer: 200  // 预缓存 200px 的额外项
}

// ❌ 错误：用 Column + Repeater（一次性创建所有项）
Column {
    Repeater {
        model: artifactModel  // 1000 项 = 1000 个组件同时创建
        delegate: ArtifactItem {}
    }
}
```

---

## 附录 A：完整架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            main.py (应用入口)                               │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                   DependencyContainer (IoC 容器)                     │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐   │   │
│  │  │ OcrWorker  │  │ ApiClient  │  │ LogBridge  │  │ Settings   │   │   │
│  │  │ (QThread)  │  │ (HTTP)     │  │ (DB+UI)    │  │ (Config)   │   │   │
│  │  └────────────┘  └────────────┘  └────────────┘  └────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       │ 注入依赖                                                             │
│       ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     Presenters (QObject)                             │   │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │   │
│  │  │ SettingsPresenter│  │ ArtifactPresenter│  │ RegionMarker     │  │   │
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       │ setContextProperty()                                                │
│       ▼                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                          QML Engine                                  │   │
│  │  ┌────────────────────────────────────────────────────────────────┐   │   │
│  │  │  Pages/ (SettingsPage.qml, DebugPage.qml, ...)                │   │   │
│  │  ├────────────────────────────────────────────────────────────────┤   │   │
│  │  │  Components/ (BaseButton.qml, ConfirmDialog.qml, ...)         │   │   │
│  │  └────────────────────────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 附录 B：技术栈速查表

| 技术 | 版本 | 用途 | 对标技术 |
|------|------|------|---------|
| Python | >= 3.13.7 | 主力语言 | Java 17+ |
| PySide6 | >= 6.7 | GUI 框架 | Vue 3 + DOM |
| PaddleOCR | >= 3.0.0 | 文字识别引擎 | Tesseract（但更快更准） |
| PaddlePaddle | >= 3.0.0, < 3.1.0 | OCR 底层框架 | CUDA + cuDNN |
| OpenCV | >= 4.10 (headless) | 图像处理 | PIL / Pillow |
| Loguru | >= 0.7 | 日志 | Logback / Winston |
| FastAPI | latest | Web API（可选） | Spring Boot Controller |
| Uvicorn | latest | ASGI 服务器 | Tomcat |
| HTTPX | >= 0.27 | HTTP 客户端 | Axios |
| PyYAML | >= 6.0 | 配置文件解析 | Jackson YAML |
| SQLite | 内置 (WAL) | 本地数据库 | H2 Database |
| Ruff | latest | Lint | ESLint |
| Black | latest | 格式化 | Prettier |
| MyPy | latest | 类型检查 | TypeScript |
| Pytest | >= 8.0 | 测试 | JUnit + Jest |

## 附录 C：新增功能开发 Checklist

```
┌─────────────────────────────────────────────────────────────────┐
│  新增功能开发标准流程                                            │
├─────────────────────────────────────────────────────────────────┤
│  □ 1. 搜索现有代码，确认无重复实现（grep + 人工检查）           │
│  □ 2. 确定新模块的位置（哪个目录、哪个文件）                    │
│  □ 3. 定义接口（函数签名 / 类接口），确保通用化                 │
│  □ 4. 实现功能，编写单元测试                                    │
│  □ 5. 如需异步执行，选择合适的线程模型（QThread / QThreadPool） │
│  □ 6. 在 DependencyContainer 中注册新服务（如需要）             │
│  □ 7. 在 Presenter 中通过构造函数注入依赖                       │
│  □ 8. 在 QML 中只做展示，业务逻辑放在 Presenter                │
│  □ 9. 所有日志使用 log，不使用 print                            │
│  □ 10. 更新本文档（DEVELOPMENT_GUIDE.md）                      │
│  □ 11. 提交 PR 前运行 ruff + black + mypy + pytest             │
└─────────────────────────────────────────────────────────────────┘
```

---
