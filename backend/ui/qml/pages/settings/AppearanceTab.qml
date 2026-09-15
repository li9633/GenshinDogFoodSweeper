import QtQuick
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

ColumnLayout {
    id: root
    Layout.fillWidth: true
    spacing: 16
    Layout.margins: 24

    Text {
        text: "外观"
        font.family: Theme.fontFamily
        font.pixelSize: 18
        font.bold: true
        color: Theme.textPrimary
    }

    GCard {
        Layout.fillWidth: true
        title: "主题模式"
        subtitle: "选择深色或浅色主题"

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Text {
                text: "主题模式"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                Layout.preferredWidth: 80
            }
            GComboBox {
                implicitWidth: 140
                model: ["深色", "浅色"]
                currentIndex: SettingsPresenter.themeIndex
                onCurrentIndexChanged: {
                    SettingsPresenter.setThemeByIndex(currentIndex)
                }
            }
        }
    }
}