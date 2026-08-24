import QtQuick
import QtQuick.Layouts
import GenshinUI
// qmllint disable unqualified

Rectangle {
    id: root
    property string pageTitle: "狗粮清理器"
    color: Theme.bgPrimary

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 20

        GButton {
            Layout.alignment: Qt.AlignHCenter
            text: DogfoodPresenter.running ? "运行中..." : "开始分解"
            colorType: "primary"
            enabled: !DogfoodPresenter.running
            onClicked: DogfoodPresenter.startDecompose()
        }

        Text {
            Layout.alignment: Qt.AlignHCenter
            text: DogfoodPresenter.status || ""
            font.family: Theme.fontFamily
            font.pixelSize: 14
            color: Theme.textSecondary
            visible: text !== ""
        }
    }
}