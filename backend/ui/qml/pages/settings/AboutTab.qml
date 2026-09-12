import QtQuick
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

ColumnLayout {
    Layout.fillWidth: true
    spacing: 16
    Layout.margins: 24

    Text {
        text: "关于"
        font.family: Theme.fontFamily
        font.pixelSize: 18
        font.bold: true
        color: Theme.textPrimary
    }

    GCard {
        Layout.fillWidth: true

        RowLayout {
            Layout.fillWidth: true

            Item { Layout.fillWidth: true }

            ColumnLayout {
                Layout.preferredWidth: 420
                Layout.maximumWidth: 420
                spacing: 12

                Image {
                    Layout.alignment: Qt.AlignHCenter
                    sourceSize.width: 88
                    sourceSize.height: 88
                    width: 88
                    height: 88
                    source: SettingsPresenter.appIconPath
                    fillMode: Image.PreserveAspectFit
                    mipmap: true
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: SettingsPresenter.appTitle
                    font.family: Theme.fontFamily
                    font.pixelSize: 20
                    font.bold: true
                    color: Theme.textPrimary
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: SettingsPresenter.appSubtitle
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                }

                Rectangle {
                    id: versionBadge
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: versionText.implicitWidth + 16
                    Layout.preferredHeight: 22
                    radius: 11
                    color: Theme.accentOverlay6

                    property bool showFull: false

                    Text {
                        id: versionText
                        anchors.centerIn: parent
                        text: versionBadge.showFull
                            ? SettingsPresenter.appVersionFull
                            : SettingsPresenter.appVersion
                        font.family: "Consolas"
                        font.pixelSize: 11
                        font.bold: true
                        color: Theme.accent
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: SettingsPresenter.isReleaseVersion
                            ? Qt.PointingHandCursor
                            : Qt.ArrowCursor
                        onClicked: {
                            if (SettingsPresenter.isReleaseVersion) {
                                versionBadge.showFull = !versionBadge.showFull
                            }
                        }
                    }

                    Behavior on Layout.preferredWidth {
                        NumberAnimation { duration: 200 }
                    }
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.fillWidth: true
                    Layout.maximumWidth: 420
                    text: SettingsPresenter.appDescription
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                    wrapMode: Text.WordWrap
                    lineHeight: 1.6
                    horizontalAlignment: Text.AlignHCenter
                }

                Row {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 20
                    GTextLink {
                        text: "项目地址 →"
                        url: SettingsPresenter.githubUrl
                    }
                    GTextLink {
                        text: "问题反馈 →"
                        url: SettingsPresenter.issuesUrl
                    }
                }

                Item { Layout.preferredHeight: 8 }

                // -- 检查更新 --
                GButton {
                    Layout.alignment: Qt.AlignHCenter
                    text: UpdatePresenter.checking ? "检查中…" : "检查更新"
                    enabled: !UpdatePresenter.checking
                    onClicked: UpdatePresenter.checkForUpdates()
                }

                Text {
                    Layout.alignment: Qt.AlignHCenter
                    visible: UpdatePresenter.errorText !== ""
                    text: UpdatePresenter.errorText
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: "#D32F2F"
                    wrapMode: Text.WordWrap
                    Layout.maximumWidth: 380
                }
            }

            Item { Layout.fillWidth: true }
        }
    }

    Item { Layout.fillHeight: true }
}