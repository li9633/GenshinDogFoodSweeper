import QtQuick
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

ColumnLayout {
    id: root
    Layout.fillWidth: true
    spacing: 16
    Layout.margins: 24

    property bool capturingHotkey: false

    Text {
        text: "快捷键"
        font.family: Theme.fontFamily
        font.pixelSize: 18
        font.bold: true
        color: Theme.textPrimary
    }

    GCard {
        Layout.fillWidth: true
        title: "终止快捷键"
        subtitle: "按下此快捷键可立即终止所有自动化操作"

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "当前快捷键"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                Layout.preferredWidth: 80
            }

            Text {
                text: root.capturingHotkey ? "请按下新快捷键…" : SettingsPresenter.hotkeyDisplay
                font.family: Theme.fontFamily
                font.pixelSize: 13
                font.bold: true
                color: root.capturingHotkey ? Theme.warning : Theme.textPrimary
            }

            Item { Layout.fillWidth: true }

            GButton {
                text: root.capturingHotkey ? "取消录制" : "修改"
                colorType: root.capturingHotkey ? "warning" : "info"
                onClicked: {
                    if (root.capturingHotkey) {
                        SettingsPresenter.cancelHotkeyCapture()
                        root.capturingHotkey = false
                    } else {
                        SettingsPresenter.startHotkeyCapture()
                        root.capturingHotkey = true
                    }
                }
            }
        }
    }

    Connections {
        target: SettingsPresenter
        function onHotkeyCaptureFinished() {
            root.capturingHotkey = false
        }
    }
}