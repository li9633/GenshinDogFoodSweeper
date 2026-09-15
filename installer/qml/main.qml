import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import InstallerUI
import './pages'
import './debug'
// qmllint disable unqualified

ApplicationWindow {
    id: root
    visible: true
    width: Theme.windowWidth
    height: Theme.windowHeight
    minimumWidth: isDebug ? 400 : Theme.windowWidth
    minimumHeight: isDebug ? 300 : Theme.windowHeight
    maximumWidth: isDebug ? 1920 : Theme.windowWidth
    maximumHeight: isDebug ? 1080 : Theme.windowHeight
    title: Coordinator.windowTitle
    color: Theme.bgWindow
    flags: Coordinator.allowClose
           ? (Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowTitleHint)
           : (Qt.Window | Qt.WindowTitleHint)

    // 页面控制
    property string currentPage: "welcome"

    Component.onCompleted: {
        Coordinator.navigateRequested.connect(function(page) {
            currentPage = page;
        });
    }

    // 页面容器
    StackLayout {
        id: stack
        anchors.fill: parent
        anchors.margins: Theme.pageMargin
        currentIndex: {
            switch (currentPage) {
            case "welcome": return 0;
            case "directory": return 1;
            case "confirm": return 2;
            case "progress": return 3;
            case "finish": return 4;
            default: return 0;
            }
        }

        WelcomePage { id: welcomePage }
        DirectoryPage { id: directoryPage }
        ConfirmPage { id: confirmPage }
        ProgressPage { id: progressPage }
        FinishPage { id: finishPage }
    }

    // 安装完成 → 跳转完成页
    Connections {
        target: ProgressPresenter
        function onInstallFinished(success, message) {
            if (success) {
                currentPage = "finish";
                if (FinishPresenter.autoLaunchOnFinish) {
                    FinishPresenter.launchApp();
                }
            } else {
                progressPage.showError(message);
            }
        }
    }

    // ── 调试面板（F12 切换） ──
    Shortcut {
        sequence: "F12"
        enabled: isDebug
        onActivated: debugPanel.visible = !debugPanel.visible
    }

    DebugPanel {
        id: debugPanel
        visible: false
    }
}