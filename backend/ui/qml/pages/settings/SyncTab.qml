import QtQuick
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

ColumnLayout {
    id: root
    Layout.fillWidth: true
    spacing: 16
    Layout.margins: 24

    property bool syncing: false
    property bool syncIndeterminate: false
    property string syncProgressText: ""

    onVisibleChanged: {
        if (visible) {
            syncProgressText = ""
            SettingsPresenter.refreshSyncInfo()
        }
    }

    Text {
        text: "同步"
        font.family: Theme.fontFamily
        font.pixelSize: 18
        font.bold: true
        color: Theme.textPrimary
    }

    GCard {
        Layout.fillWidth: true
        title: "圣遗物数据同步"
        subtitle: "从米游社同步圣遗物数据到本地数据库"

        ColumnLayout {
            spacing: 12

            GButton {
                text: root.syncing ? "同步中…" : "立即同步"
                enabled: !root.syncing
                onClicked: {
                    root.syncing = true
                    root.syncIndeterminate = true
                    root.syncProgressText = "正在拉取圣遗物套装…"
                    SettingsPresenter.startSync()
                }
            }

            GProgressBar {
                id: syncBar
                Layout.fillWidth: true
                indeterminate: root.syncIndeterminate
                value: 0
                progressText: root.syncProgressText
                visible: root.syncing
            }

            Row {
                spacing: 16
                Text {
                    text: SettingsPresenter.syncTime
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textSecondary
                }
                Text {
                    text: SettingsPresenter.syncStats
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textSecondary
                }
            }

            Text {
                text: SettingsPresenter.dbStats
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textSecondary
            }
        }
    }

    GCard {
        Layout.fillWidth: true
        title: "同步版本检查"
        subtitle: "设置圣遗物数据版本检查的频率"

        RowLayout {
            Layout.fillWidth: true
            spacing: 12
            Text {
                text: "检查频率"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                Layout.preferredWidth: 80
            }
            GComboBox {
                implicitWidth: 140
                model: SettingsPresenter.versionCheckIntervalLabels
                currentIndex: SettingsPresenter.versionCheckIntervalIndex
                onCurrentIndexChanged: {
                    SettingsPresenter.setVersionCheckIntervalByIndex(currentIndex)
                }
            }
        }
    }

    Connections {
        target: SettingsPresenter
        function onSyncProgress(current, total, text) {
            if (total > 0) {
                root.syncIndeterminate = false
                syncBar.value = current / total
                root.syncProgressText = text + " " + current + " / " + total
            } else {
                root.syncProgressText = text
            }
        }
        function onSyncFinished(setCount, slotCount, expectedCount) {
            root.syncing = false
            root.syncIndeterminate = false
            root.syncProgressText = ""
        }
        function onSyncFailed(error) {
            root.syncing = false
            root.syncIndeterminate = false
            root.syncProgressText = ""
        }
    }
}