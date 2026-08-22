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
    visible: true
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
}