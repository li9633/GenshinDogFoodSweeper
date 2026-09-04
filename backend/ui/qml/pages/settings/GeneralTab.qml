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
        text: "通用"
        font.family: Theme.fontFamily
        font.pixelSize: 18
        font.bold: true
        color: Theme.textPrimary
    }

    GCard {
        Layout.fillWidth: true
        title: "日志等级"

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Text {
                text: "日志等级"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                Layout.preferredWidth: 80
            }
            GComboBox {
                implicitWidth: 160
                model: SettingsPresenter.logLevelLabels
                currentIndex: SettingsPresenter.logLevelIndex
                onActivated: SettingsPresenter.setLogLevelByIndex(currentIndex)
            }
        }
    }
}