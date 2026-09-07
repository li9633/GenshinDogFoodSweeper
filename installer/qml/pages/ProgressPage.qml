import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    property int progressValue: 0
    property string statusText: "准备中..."
    property bool hasError: false
    property string errorMessage: ""

    function showError(msg) {
        hasError = true;
        errorMessage = msg;
        statusText = "安装失败";
    }

    Connections {
        target: InstallerPresenter
        function onInstallProgress(pct, status) {
            progressValue = pct;
            statusText = status;
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingLg

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "heading"
            text: InstallerPresenter.mode === "update" ? "正在更新..." : "正在安装..."
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "normal"
            text: statusText
            color: hasError ? Theme.error : Theme.subtleText
        }

        IProgressBar {
            Layout.alignment: Qt.AlignHCenter
            value: progressValue / 100.0
            indeterminate: progressValue === 0 && !hasError
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "normal"
            visible: progressValue > 0
            text: progressValue + "%"
            color: Theme.secondaryText
        }

        // 错误信息
        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "small"
            visible: hasError
            text: errorMessage
            color: Theme.error
        }

        Item { Layout.fillHeight: true }
    }

    // 底部按钮
    RowLayout {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.bottomMargin: Theme.spacingMd

        IButton {
            visible: hasError
            text: "退出"
            onClicked: InstallerPresenter.quit()
        }
    }
}