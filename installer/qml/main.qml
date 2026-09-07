import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import InstallerUI
import './pages'
// qmllint disable unqualified

ApplicationWindow {
    id: root
    visible: true
    width: Theme.windowWidth
    height: Theme.windowHeight
    minimumWidth: Theme.windowWidth
    minimumHeight: Theme.windowHeight
    maximumWidth: Theme.windowWidth
    maximumHeight: Theme.windowHeight
    title: Theme.windowTitle
    color: Theme.bgWindow
    flags: Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowTitleHint

    // 页面控制
    property string currentPage: "welcome"

    Component.onCompleted: {
        InstallerPresenter.navigateRequested.connect(function(page) {
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
                case "progress": return 2;
                case "finish": return 3;
                default: return 0;
            }
        }

        WelcomePage { id: welcomePage }
        DirectoryPage { id: directoryPage }
        ProgressPage { id: progressPage }
        FinishPage { id: finishPage }
    }

    // 安装完成 → 跳转完成页
    Connections {
        target: InstallerPresenter
        function onInstallFinished(success, message) {
            if (success) {
                currentPage = "finish";
            } else {
                progressPage.showError(message);
            }
        }
    }
}