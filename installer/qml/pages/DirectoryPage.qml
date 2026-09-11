import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import '../InstallerUI'
// qmllint disable unqualified

ColumnLayout {
    id: page

    visible: DirectoryPresenter.showDirectoryPage
    spacing: 0

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

    // ═══════════════════════════════════════════
    // Hero 区：标题
    // ═══════════════════════════════════════════
    ILabel {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 8
        Layout.bottomMargin: 12
        labelType: "heading"
        text: "选择安装目录"
    }

    // ═══════════════════════════════════════════
    // Content 卡片
    // ═══════════════════════════════════════════
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.bottomMargin: 12
        color: Theme.bgWhite
        radius: 8
        border.color: Theme.separator
        border.width: 1
        clip: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: Theme.spacingMd

            ILabel {
                Layout.alignment: Qt.AlignHCenter
                labelType: "body"
                text: DirectoryPresenter.hintText
            }

            RowLayout {
                Layout.fillWidth: true
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
                Layout.fillWidth: true
                labelType: "small"
                text: DirectoryPresenter.requiredSpaceText
            }

            ILabel {
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true
                labelType: "small"
                visible: DirectoryPresenter.freeSpaceText !== ""
                text: DirectoryPresenter.freeSpaceText
            }

            ILabel {
                Layout.alignment: Qt.AlignHCenter
                Layout.fillWidth: true
                labelType: "small"
                wrapMode: Text.WordWrap
                visible: !DirectoryPresenter.canInstall
                text: DirectoryPresenter.cannotInstallReason
                color: Theme.error
            }

            Item { Layout.fillHeight: true }
        }
    }

    // ═══════════════════════════════════════════
    // Actions 区
    // ═══════════════════════════════════════════
    RowLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignRight

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