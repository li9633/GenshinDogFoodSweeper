import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// SettingsPresenter 是 Python 上下文属性；syncing/downloading 等是根元素属性，qmllint 无法跨层级识别

Rectangle {
    id: root
    color: Theme.bgPrimary

    // ============================================================
    // 内部状态（仅 UI 控制，业务数据直接绑定 SettingsPresenter）
    // ============================================================
    property bool syncing: false
    property bool downloading: false
    property string syncProgressText: ""
    property string modelProgressText: ""

    // 页面可见时刷新数据（等价于 Python 版 showEvent）
    onVisibleChanged: {
        if (visible) {
            // 触发 Property 重新求值，刷新同步时间和模型状态
            syncProgressText = ""
            modelProgressText = ""
        }
    }

    // ============================================================
    // 滚动区域
    // ============================================================
    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 16
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 12

            // -- 标题 --
            Text {
                text: "设置"
                font.family: Theme.fontFamily
                font.pixelSize: 18
                font.bold: true
                color: Theme.accent
            }

            // ======== 外观设置 ========
            GroupBox { padding: 10
                title: "外观设置"
                Layout.fillWidth: true
                background: Rectangle {
                    color: Theme.bgSecondary
                    radius: Theme.radius
                    border.color: Theme.border
                }
                label: Text {
                    text: "外观设置"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                    color: Theme.textPrimary
                    // qmllint disable missing-property
                    x: parent.leftPadding
                }

                RowLayout {
                    anchors.fill: parent
                    spacing: 8

                    Text {
                        text: "主题:"
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        color: Theme.textPrimary
                    }

                    GComboBox {
                        id: themeCombo
                        model: ["深色", "浅色"]
                        currentIndex: SettingsPresenter.themeIndex
                        onCurrentIndexChanged: SettingsPresenter.setThemeByIndex(currentIndex)
                    }
                }
            }

            // ======== 圣遗物同步 ========
            GroupBox {
                title: "圣遗物同步"
                Layout.fillWidth: true
                background: Rectangle {
                    color: Theme.bgSecondary
                    radius: Theme.radius
                    border.color: Theme.border
                }
                label: Text {
                    text: "圣遗物同步"
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    font.bold: true
                    color: Theme.textPrimary
                    // qmllint disable missing-property
                    x: parent.leftPadding
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    // 按钮行
                    RowLayout {
                        spacing: 8

                        GButton {
                            text: syncing ? "同步中…" : "立即同步"
                            colorType: "primary"
                            enabled: !syncing
                            onClicked: SettingsPresenter.startSync()
                        }
                    }

                    // 进度条（带居中百分比）
                    ProgressBar {
                        id: syncProgress
                        Layout.fillWidth: true
                        Layout.preferredHeight: 18
                        visible: syncing
                        indeterminate: true

                        background: Rectangle {
                            color: Theme.bgTrack
                            radius: 4
                        }
                        contentItem: Item {
                            implicitWidth: 200
                            implicitHeight: 18
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: syncProgress.indeterminate
                                       ? parent.width * 0.3
                                       : syncProgress.visualPosition * parent.width
                                height: 6
                                radius: 3
                                color: Theme.accent
                            }
                            Text {
                                anchors.centerIn: parent
                                text: syncProgress.indeterminate
                                      ? "--%"
                                      : Math.round(syncProgress.value / syncProgress.to * 100) + "%"
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: Theme.textSecondary
                            }
                        }
                    }

                    // 状态文字（同步中显示进度，完成后 show 最新数据）
                    Text {
                        text: syncing ? ("正在同步… " + syncProgressText) : SettingsPresenter.syncTime
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
            }

            // ======== OCR 模型 ========
            GroupBox {
                title: "OCR 模型"
                Layout.fillWidth: true
                padding: 10
                background: Rectangle {
                    color: Theme.bgSecondary
                    radius: Theme.radius
                    border.color: Theme.border
                }
                label: Text {
                    text: "OCR 模型"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                    color: Theme.textPrimary
                    // qmllint disable missing-property
                    x: parent.leftPadding
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    // 按钮行
                    RowLayout {
                        spacing: 8

                        GButton {
                            text: downloading ? "下载中…"
                                 : SettingsPresenter.modelReady ? "重新下载"
                                 : "下载模型"
                            colorType: "primary"
                            enabled: !downloading
                            onClicked: SettingsPresenter.downloadModels()
                        }
                    }

                    // 进度条（带居中百分比）
                    ProgressBar {
                        id: modelProgress
                        Layout.fillWidth: true
                        Layout.preferredHeight: 18
                        visible: downloading
                        indeterminate: true

                        background: Rectangle {
                            color: Theme.bgTrack
                            radius: 4
                        }
                        contentItem: Item {
                            implicitWidth: 200
                            implicitHeight: 18
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: modelProgress.indeterminate
                                       ? parent.width * 0.3
                                       : modelProgress.visualPosition * parent.width
                                height: 6
                                radius: 3
                                color: Theme.accent
                            }
                            Text {
                                anchors.centerIn: parent
                                text: modelProgress.indeterminate
                                      ? "--%"
                                      : Math.round(modelProgress.value / modelProgress.to * 100) + "%"
                                font.family: Theme.fontFamily
                                font.pixelSize: 11
                                color: Theme.textSecondary
                            }
                        }
                    }

                    // 状态文字（下载中显示进度，完成后 show 最新数据）
                    Text {
                        text: downloading ? ("正在下载… " + modelProgressText) : SettingsPresenter.modelStatus
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }

                    Text {
                        text: SettingsPresenter.modelVersion
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textSecondary
                    }
                }
            }

            // 底部留白
            Item { Layout.fillHeight: true }
        }
    }

    // ============================================================
    // 后端信号连接
    // ============================================================
    Connections {
        target: SettingsPresenter

        function onThemeChanged(theme) {
            themeCombo.currentIndex = (theme === "dark") ? 0 : 1
        }

        function onSyncStarted() {
            syncing = true
        }

        function onSyncProgress(current, total, name) {
            syncProgress.indeterminate = false
            syncProgress.from = 0
            syncProgress.to = total
            syncProgress.value = current
            syncProgressText = current + "/" + total
        }

        function onSyncFinished(sets, slots, expected) {
            syncing = false
            syncProgressText = ""
        }

        function onSyncFailed(error) {
            syncing = false
            syncProgressText = ""
        }

        function onModelDownloadStarted() {
            downloading = true
        }

        function onModelDownloadProgress(current, total, status) {
            modelProgress.indeterminate = false
            modelProgress.from = 0
            modelProgress.to = total
            modelProgress.value = current
            modelProgressText = current + "/" + total
        }

        function onModelDownloadFinished(success, message) {
            downloading = false
            modelProgressText = ""
        }
    }
}