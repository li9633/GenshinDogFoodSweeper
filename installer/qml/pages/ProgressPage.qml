import QtQuick
import QtQuick.Layouts
import '../InstallerUI'
// qmllint disable unqualified missing-property

ColumnLayout {
    id: page

    spacing: 0

    property int progressValue: 0
    property string statusText: "准备中..."
    property bool hasError: false
    property string errorMessage: ""

    readonly property color progressColor: ProgressPresenter.progressColor

    function showError(msg) {
        hasError = true;
        errorMessage = msg;
        statusText = "操作失败";
    }

    Connections {
        target: ProgressPresenter
        function onInstallProgress(pct, status) {
            progressValue = pct;
            statusText = status;
        }
    }

    // ═══════════════════════════════════════════
    // Hero 区：标题
    // ═══════════════════════════════════════════
    ILabel {
        Layout.alignment: Qt.AlignHCenter
        Layout.topMargin: 8
        Layout.bottomMargin: 12
        labelType: "heading"
        text: ProgressPresenter.progressTitle
    }

    // ═══════════════════════════════════════════
    // Content 卡片
    // ═══════════════════════════════════════════
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.bottomMargin: 12
        color: Theme.bgWhite
        radius: 8
        border.color: Theme.separator
        border.width: 1
        clip: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 16
            spacing: Theme.spacingMd

            ILabel {
                Layout.alignment: Qt.AlignHCenter
                labelType: "normal"
                text: statusText
                color: hasError ? Theme.error : Theme.subtleText
            }

            IProgressBar {
                id: progressBar
                Layout.alignment: Qt.AlignHCenter
                value: progressValue / 100.0
                indeterminate: progressValue === 0 && !hasError
                accentColor: progressColor
            }

            ILabel {
                Layout.alignment: Qt.AlignHCenter
                labelType: "normal"
                visible: progressValue > 0
                text: progressValue + "%"
                color: progressColor
            }

            ILabel {
                Layout.fillWidth: true
                labelType: "small"
                wrapMode: Text.WordWrap
                visible: hasError
                text: errorMessage
                color: Theme.error
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: ProgressPresenter.showLog
                color: "#1A000000"
                radius: 4
                clip: true

                ListView {
                    id: logView
                    anchors.fill: parent
                    anchors.margins: 4
                    model: ProgressPresenter.installLog
                    spacing: 2
                    delegate: Text {
                        width: logView.width
                        text: modelData
                        color: Theme.subtleText
                        font.pixelSize: 11
                        elide: Text.ElideLeft
                    }
                    onCountChanged: positionViewAtEnd()
                }
            }

            Item {
                Layout.fillHeight: true
                visible: !ProgressPresenter.showLog
            }
        }
    }

    // ═══════════════════════════════════════════
    // Actions 区
    // ═══════════════════════════════════════════
    RowLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignRight

        IButton {
            visible: hasError
            text: "退出"
            onClicked: ProgressPresenter.quit()
        }
    }
}