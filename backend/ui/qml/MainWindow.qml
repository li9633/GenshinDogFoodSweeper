import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI
import "components"
import "pages"

// qmllint disable unqualified missing-property
// EnvManager / SettingsPresenter 是 Python 通过 setContextProperty 注入的上下文属性
// stackView.currentItem.pageTitle 是页面组件声明的动态属性

ApplicationWindow {
    id: root
    visible: false
    width: 1200
    height: 800
    minimumWidth: 900
    minimumHeight: 600
    color: Theme.bgPrimary
    title: EnvManager.isDebug
           ? "原神狗粮清扫器（调试模式）"
           : "原神狗粮清扫器"

    // ============================================================
    // 主布局：侧边栏 + 内容区 + 状态栏
    // ============================================================
    Component.onCompleted: {
        Theme.isDark = SettingsPresenter.currentTheme === "dark"
        root.visible = true
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 0

            // -- 左侧导航栏 --
            Sidebar {
                id: sidebar
                Layout.preferredWidth: 160
                Layout.fillHeight: true
                currentKey: "dogfood"

                onPageSelected: function(key) {
                    if (sidebar.currentKey === key) return;
                    sidebar.currentKey = key
                    stackView.replace(null, getPageComponent(key), StackView.Immediate)
                }
            }

            // -- 分割线 --
            Rectangle {
                Layout.preferredWidth: 1
                Layout.fillHeight: true
                color: Theme.border
            }

            // -- 右侧内容区 --
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // 顶部工具栏
                Toolbar {
                    Layout.fillWidth: true
                    pageTitle: stackView.currentItem ? stackView.currentItem.pageTitle || "" : ""
                }

                // 分割线
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 1
                    color: Theme.border
                }

                // 页面容器
                StackView {
                    id: stackView
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    initialItem: dogfoodPage
                }
            }
        }

        // -- 底部状态栏 --
        StatusBar {
            Layout.fillWidth: true
        }
    }

    // ============================================================
    // 页面组件工厂
    // ============================================================
    function getPageComponent(key) {
        switch (key) {
            case "dogfood":  return dogfoodPage
            case "scanner":  return scannerPage
            case "locker":   return lockerPage
            case "rules":    return rulesPage
            case "settings": return settingsPage
            case "debug":    return debugPage
            default:         return dogfoodPage
        }
    }

    Component { id: dogfoodPage;  DogfoodPage {} }
    Component { id: scannerPage;  ScannerPage {} }
    Component { id: lockerPage;   LockerPage {} }
    Component { id: rulesPage;    RulesPage {} }
    Component { id: settingsPage; SettingsPage {} }
    Component { id: debugPage;    DebugPage {} }

    // ============================================================
    // 主题同步：SettingsPresenter.themeChanged → Theme.isDark
    // ============================================================
    Connections {
        target: SettingsPresenter
        function onThemeChanged(theme) {
            Theme.isDark = theme === "dark"
        }
    }

    // ============================================================
    // 版本更新 → 导航到同步Tab
    // ============================================================
    Connections {
        target: VersionCheck
        function onNavigateToSyncTab() {
            sidebar.currentKey = "settings"
            stackView.replace(null, settingsPage, StackView.Immediate)
            if (stackView.currentItem) {
                stackView.currentItem.currentTab = 1
            }
        }
    }

    // ============================================================
    // Python 信号桥接弹窗（GMessageBox.error / warning / info / success）
    // ============================================================
    Connections {
        target: GMessageBoxBridge
        function onShowMessage(msgType, msgText, bringToFront) {
                pythonMsgBox.msgType = msgType
                pythonMsgBox.msgText = msgText
                pythonMsgBox.bringToFront = bringToFront
                pythonMsgBox.buttonModel = []
                pythonMsgBox.open()
            }
            function onShowDialog(msgType, title, msgText, bringToFront, buttonsJson) {
                pythonMsgBox.msgType = msgType
                pythonMsgBox.title = title
                pythonMsgBox.msgText = msgText
                pythonMsgBox.bringToFront = bringToFront
                pythonMsgBox.buttonModel = JSON.parse(buttonsJson)
                pythonMsgBox.open()
            }
    }

    GMessageBox {
        id: pythonMsgBox
        onButtonClicked: function(role) {
            GMessageBoxBridge.handleButtonClicked(role)
        }
    }

    // ============================================================
    // 开发版水印（Canvas 叠加，仅 DEV/ALPHA 渠道显示，不拦截鼠标）
    // ============================================================
    Canvas {
        id: devWatermark
        anchors.fill: parent
        z: 9999
        visible: SettingsPresenter.isDevVersion
        enabled: false

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            ctx.save();

            ctx.translate(width / 2, height / 2);
            ctx.rotate(-25 * Math.PI / 180);
            ctx.font = "12px '" + Theme.fontFamily + "'";
            ctx.fillStyle = "rgba(255, 80, 80, 0.10)";
            ctx.textAlign = "center";

            var text = "内部开发版本，不代表最终品质";
            var rowSpacing = 130;
            var colSpacing = 380;
            var cols = Math.ceil(width / colSpacing) + 2;
            var rows = Math.ceil(height / rowSpacing) + 2;

            for (let row = -rows; row < rows; row++) {
                for (let col = -cols; col < cols; col++) {
                    ctx.fillText(text, col * colSpacing, row * rowSpacing);
                }
            }

            ctx.restore();
        }
    }
}