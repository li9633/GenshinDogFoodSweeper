import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    property alias installDir: dirInput.text

    FolderDialog {
        id: folderDialog
        title: "选择安装目录"
        currentFolder: "file:///" + dirInput.text
        onAccepted: {
            let path = selectedFolder.toString();
            // 去掉 file:/// 前缀
            if (path.startsWith("file:///")) {
                path = path.substring(8);
            }
            dirInput.text = path;
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
                text: InstallerPresenter.installDir
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
            text: "所需空间: 约 800 MB"
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
            text: "安装"
            btnType: "primary"
            font.bold: true
            enabled: dirInput.text.length > 0
            onClicked: {
                InstallerPresenter.setInstallDir(dirInput.text);
                InstallerPresenter.navigateTo("progress");
                InstallerPresenter.startInstall();
            }
        }
    }
}