import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    visible: WelcomePresenter.mode !== "uninstall" && !Coordinator.quickUpdate

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingLg

        // 图标
        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 36
            Layout.preferredHeight: 36
            source: WelcomePresenter.pageIcon
            fillMode: Image.PreserveAspectFit
        }

        // 标题
        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "title"
            visible: !WelcomePresenter.isUpdateMode
            text: WelcomePresenter.pageTitle
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "heading"
            visible: WelcomePresenter.isUpdateMode
            text: WelcomePresenter.pageTitle
            color: "#4CAF50"
        }

        // 版本号
        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "normal"
            visible: WelcomePresenter.versionLabel !== ""
            text: WelcomePresenter.versionLabel
            color: WelcomePresenter.isUpdateMode ? "#4CAF50" : Theme.secondaryText
        }

        // 分隔线
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            Layout.topMargin: 8
            Layout.bottomMargin: 8
            color: WelcomePresenter.isUpdateMode ? "#A5D6A7" : Theme.separator
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            labelType: "body"
            text: WelcomePresenter.welcomeText
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
            onClicked: WelcomePresenter.quit()
        }

        IButton {
            text: WelcomePresenter.actionButtonText
            btnType: "primary"
            font.bold: true
            onClicked: {
                WelcomePresenter.nextStep();
            }
        }
    }
}