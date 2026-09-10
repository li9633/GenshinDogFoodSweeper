import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified

Item {
    id: page

    ColumnLayout {
        anchors.centerIn: parent
        spacing: Theme.spacingLg

        // 图标
        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 80
            Layout.preferredHeight: 80
            source: ConfirmPresenter.pageIcon
            fillMode: Image.PreserveAspectFit
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "heading"
            text: ConfirmPresenter.pageTitle
            color: "#D32F2F"
        }

        // 警告卡片
        Rectangle {
            id: warningCard
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Theme.contentWidth
            Layout.preferredHeight: warningLabel.implicitHeight + 24
            color: "#FFF3F3"
            border.color: "#FFCDD2"
            border.width: 1
            radius: 6

            ILabel {
                id: warningLabel
                anchors.centerIn: parent
                width: parent.width - 24
                labelType: "body"
                text: ConfirmPresenter.warningText
                lineHeight: 1.5
                wrapMode: Text.WordWrap
            }
        }

        ILabel {
            Layout.alignment: Qt.AlignHCenter
            labelType: "small"
            text: "此操作不可撤销，请确认后再操作。"
            color: "#D32F2F"
        }

        Item { Layout.fillHeight: true }
    }

    // 底部按钮
    RowLayout {
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.bottomMargin: Theme.spacingMd

        IButton {
            text: "我再想想"
            btnType: "flat"
            onClicked: ConfirmPresenter.quit()
        }

        IButton {
            text: ConfirmPresenter.actionButtonText
            btnType: "danger"
            font.bold: true
            onClicked: {
                ConfirmPresenter.startUninstall();
            }
        }
    }
}