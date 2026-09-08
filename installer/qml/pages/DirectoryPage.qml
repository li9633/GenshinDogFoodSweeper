import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    visible: InstallerPresenter.showDirectoryPage

    property alias installDir: dirInput.text

    FolderDialog {
        id: folderDialog
        title: "选择安装目录"
        onAccepted: {
            let path = selectedFolder.toString();
            if (path.startsWith("file:///")) {
                path = path.substring(8);
            }
            InstallerPresenter.selectInstallDir(path);
        }
    }

    Timer {
        id: spaceTimer
        interval: 300
        onTriggered: InstallerPresenter.checkFreeSpace(dirInput.text)
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
                text: InstallerPresenter.installDir
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
            text: InstallerPresenter.requiredSpaceText
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "small"
            visible: InstallerPresenter.freeSpaceText !== ""
            text: InstallerPresenter.freeSpaceText
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "small"
            wrapMode: Text.WordWrap
            visible: !InstallerPresenter.canInstall
            text: InstallerPresenter.cannotInstallReason
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
            onClicked: InstallerPresenter.quit()
        }

        IButton {
            text: "上一步"
            btnType: "flat"
            onClicked: InstallerPresenter.navigateTo("welcome")
        }

        IButton {
            text: InstallerPresenter.actionButtonText
            btnType: "primary"
            font.bold: true
            enabled: dirInput.text.length > 0 && InstallerPresenter.canInstall
            onClicked: {
                InstallerPresenter.setInstallDir(dirInput.text);
                InstallerPresenter.navigateTo("progress");
                InstallerPresenter.startAction();
            }
        }
    }
}