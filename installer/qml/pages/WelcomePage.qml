import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingLg

        // 标题
        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "title"
            text: InstallerPresenter.appName
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "normal"
            text: InstallerPresenter.versionLabel
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            Layout.topMargin: 8
            Layout.bottomMargin: 8
            color: Theme.separator
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "body"
            text: "欢迎使用原神狗粮扫荡器安装向导。\n\n本程序将引导您完成安装过程。\n请点击「下一步」继续。"
            lineHeight: 1.6
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
            text: "下一步"
            btnType: "primary"
            font.bold: true
            onClicked: InstallerPresenter.navigateTo("directory")
        }
    }
}