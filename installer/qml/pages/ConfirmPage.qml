import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingLg

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "heading"
            text: "确认卸载"
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "body"
            text: "确定要卸载 " + InstallerPresenter.appName + " 吗？\n\n安装目录将被删除：\n" + InstallerPresenter.installDir
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "small"
            text: "此操作不可撤销，请确认后再操作。"
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
            text: InstallerPresenter.actionButtonText
            btnType: "primary"
            font.bold: true
            onClicked: {
                InstallerPresenter.navigateTo("progress");
                InstallerPresenter.startAction();
            }
        }
    }
}