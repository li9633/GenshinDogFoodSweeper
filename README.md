# 原神狗粮清扫器

> 基于 OCR + 计算机视觉的《原神》圣遗物自动化管理工具，支持全量扫描、规则锁定、一键分解。

## ✨ 功能

- **全量扫描** — 自动遍历背包全部圣遗物，OCR 识别主词条、副词条、套装等完整属性
- **智能锁定/解锁** — 根据自定义狗粮规则自动标记锁定/弃置状态，支持批量操作
- **一键分解** — 自动进入分解页面，按规则批量选择并分解低星圣遗物
- **灵活规则引擎** — 按部位、主词条、套装、副词条数值自由组合筛选条件，优先级排序命中即停
- **多格式保存** — 扫描结果支持 GDFS（自描述 JSON）格式导出，可离线复算
- **自动更新** — 启动时检测 GitHub Releases，一键下载安装新版本
- **系统托盘** — 最小化到托盘运行，支持热键操作

## 📥 下载

前往 [Releases](https://github.com/li9633/GenshinDogFoodSweeper/releases) 页面下载最新版本：

| 文件 | 说明 |
|---|---|
| `*-setup.exe` | 安装版（推荐），自动创建桌面快捷方式和开始菜单条目 |
| `*.zip` | 便携版，解压后运行 `GenshinDogFoodSweeper.exe` 即可 |

> **系统要求：** Windows 10/11，原神窗口分辨率 1920×1080（全屏窗口模式）。

## 🚀 快速开始

1. 下载安装程序或便携版
2. 启动《原神》，进入**圣遗物背包界面**
3. 运行清扫器，点击对应功能按钮：
   - **扫描** — 识别背包内所有圣遗物并保存结果
   - **锁定** — 按规则自动锁定/解锁圣遗物
   - **分解** — 按规则自动选择并分解低星圣遗物
4. 在「规则」页面自定义你的筛选规则
5. 在「设置」页面下载 OCR 模型、调整日志级别

> [!IMPORTANT]
> 首次使用需在设置页下载 OCR 模型，请确保网络畅通。
>
> 首次使用需在设置页同步最新圣遗物套装信息，确保网络畅通。

## 🛠 开发

### 环境要求

- Python ≥ 3.13.7
- [uv](https://docs.astral.sh/uv/) 包管理器

### 克隆项目

```bash
git clone git@github.com:li9633/GenshinDogFoodSweeper.git
cd GenshinDogFoodSweeper
```

### 安装依赖

```bash
uv sync
```

### 运行

```bash
uv run python -m backend.main
```

### 运行测试

```bash
uv run pytest
```

### 代码检查

```bash
uv run ruff check .
```

## 📦 构建

项目使用统一的构建脚本，一行命令即可完成打包：

```bash
# 开发渠道打包（仅 PyInstaller）
uv run python build.py

# 正式版完整构建（打包 + 安装程序 + ZIP 发布包）
uv run python build.py --channel release --installer --zip --clear

# 查看完整选项
uv run python build.py --help
```

构建产物输出到 `dist/` 目录。

## 📁 项目结构

```
GenshinDogFoodSweeper/
├── backend/                  # 主程序
│   ├── api/                  # FastAPI 服务（QML 通信桥梁）
│   ├── automation/           # 自动化核心
│   │   ├── sweep.py          # 逐格遍历引擎（扫描/锁定/分解共用）
│   │   ├── artifact_scanner.py   # 全量扫描
│   │   ├── artifact_locker.py    # 自动锁定/解锁
│   │   ├── artifact_decomposer.py # 自动分解
│   │   ├── dogfood_rule_engine.py # 狗粮规则引擎
│   │   ├── ocr_engine.py     # OCR 识别
│   │   └── ...
│   ├── contracts/            # 契约接口
│   ├── database/             # SQLite 数据持久化
│   ├── domain/               # 领域逻辑
│   ├── features/             # 独立功能模块
│   │   ├── artifact_save/    # 扫描结果保存（GDFS 等格式）
│   │   └── update/           # 自动更新
│   ├── models/               # 数据模型
│   ├── ui/                   # PySide6 + QML 界面
│   │   ├── qml/GenshinUI/    # 自定义 QML 组件库
│   │   └── presenters/       # MVP Presenter 层
│   └── main.py               # 程序入口
├── common/                   # 主程序与安装程序共享模块
├── installer/                # 安装程序（独立 PySide6 + QML 应用）
├── build_support/            # 构建系统
├── resources/                # 静态资源（模板图片、图标）
├── tests/                    # 测试
└── build.py                  # 统一构建入口
```

## 🔧 技术栈

| 分类 | 技术 |
|---|---|
| GUI 框架 | PySide6 + QML |
| OCR | PaddleOCR 3.0 |
| 计算机视觉 | OpenCV |
| 自动化控制 | PyDirectInput, PyAutoGUI, PyWin32 |
| 后端服务 | FastAPI + Uvicorn |
| 数据持久化 | SQLAlchemy + SQLite |
| 打包 | PyInstaller |
| 包管理 | uv |
| 代码质量 | Ruff, pytest |

## 📄 许可证

[MIT](LICENSE)

---

**免责声明：** 本工具仅供学习交流使用。使用本工具产生的任何游戏账号风险由使用者自行承担。