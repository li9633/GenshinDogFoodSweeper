import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    visible: DirectoryPresenter.showDirectoryPage

    property alias installDir: dirInput.text

    FolderDialog {
        id: folderDialog
        title: "选择安装目录"
        onAccepted: {
            let path = String(selectedFolder);
            if (path.startsWith("file:///")) {
                path = decodeURIComponent(path.substring(8));
            }
            DirectoryPresenter.selectInstallDir(path);
        }
    }

    Timer {
        id: spaceTimer
        interval: 300
        onTriggered: DirectoryPresenter.checkFreeSpace(dirInput.text)
    }

    Connections {
        target: DirectoryPresenter
        function onInstallDirChanged() {
            dirInput.text = DirectoryPresenter.installDir;
        }
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingLg

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "heading"
            text: "选择安装目录"
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "body"
            text: "请选择原神狗粮扫荡器的安装位置。"
        }

        // 路径输入
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            spacing: Theme.spacingSm

            ITextField {
                id: dirInput
                Layout.fillWidth: true
                text: DirectoryPresenter.installDir
                onTextChanged: spaceTimer.restart()
            }

            IButton {
                text: "浏览..."
                onClicked: folderDialog.open()
            }
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "small"
            text: DirectoryPresenter.requiredSpaceText
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "small"
            visible: DirectoryPresenter.freeSpaceText !== ""
            text: DirectoryPresenter.freeSpaceText
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "small"
            wrapMode: Text.WordWrap
            visible: !DirectoryPresenter.canInstall
            text: DirectoryPresenter.cannotInstallReason
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
            text: "取消"
            btnType: "flat"
            onClicked: DirectoryPresenter.quit()
        }

        IButton {
            text: "上一步"
            btnType: "flat"
            onClicked: DirectoryPresenter.navigateTo("welcome")
        }

        IButton {
            text: DirectoryPresenter.actionButtonText
            btnType: "primary"
            font.bold: true
            enabled: dirInput.text.length > 0 && DirectoryPresenter.canInstall
            onClicked: {
                DirectoryPresenter.setInstallDir(dirInput.text);
                DirectoryPresenter.startInstall();
            }
        }
    }
}