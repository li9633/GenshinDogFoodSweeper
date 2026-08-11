import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

Rectangle {
    color: "transparent"
    Layout.fillWidth: true
    Layout.fillHeight: true

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 12
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 8

            // ---- 添加检测条件 ----
            GroupBox {
                title: "添加检测条件"
                Layout.fillWidth: true
                background: Rectangle {
                    color: Theme.bgSecondary
                    radius: Theme.radius
                    border.color: Theme.border
                }
                label: Text {
                    text: "添加检测条件"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                    color: Theme.textPrimary
                    x: parent.leftPadding
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 6

                    // 搜索 + 刷新
                    RowLayout {
                        spacing: 4
                        TextField {
                            id: searchInput
                            Layout.fillWidth: true
                            placeholderText: "搜索模板…"
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            color: Theme.textPrimary
                            background: Rectangle {
                                color: Theme.bgTrack
                                radius: 4
                                border.color: Theme.border
                            }
                        }
                        Button {
                            text: "⟳"
                            implicitWidth: 30; implicitHeight: 30
                            contentItem: Text {
                                text: parent.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                color: Theme.textPrimary
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle { color: Theme.bgTrack; radius: 4 }
                        }
                    }

                    // 模板 + 阈值 + 添加
                    RowLayout {
                        spacing: 4
                        Text { text: "模板:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                        ComboBox {
                            id: templateCombo
                            Layout.fillWidth: true
                            model: ["请选择模板…"]
                            background: Rectangle {
                                color: Theme.bgTrack
                                radius: 4
                                border.color: Theme.border
                            }
                            contentItem: Text {
                                text: templateCombo.displayText
                                font.family: Theme.fontFamily
                                font.pixelSize: 13
                                color: Theme.textPrimary
                                verticalAlignment: Text.AlignVCenter
                                leftPadding: 8
                            }
                        }
                        Text { text: "阈值:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                        SpinBox {
                            id: spinThreshold
                            Layout.preferredWidth: 70
                            from: 0; to: 100
                            value: 80
                            editable: true
                        }
                        Button {
                            text: "+ 添加"
                            implicitHeight: 30
                            contentItem: Text {
                                text: parent.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: Theme.bgPrimary
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle { color: Theme.accent; radius: Theme.radius }
                        }
                    }

                    // 预览 + 限定区域
                    RowLayout {
                        spacing: 6

                        Rectangle {
                            width: 100; height: 80
                            color: "#2b2b2b"
                            border.color: Theme.border
                            radius: 2
                            Text {
                                anchors.centerIn: parent
                                text: "无预览"
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: "#888"
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4

                            RowLayout {
                                spacing: 2
                                CheckBox {
                                    id: chkRegion
                                    text: "限定区域"
                                    contentItem: Text {
                                        text: parent.text
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.textPrimary
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                }
                                Text { text: "X:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                                SpinBox { id: spinRx; Layout.preferredWidth: 55; from: 0; to: 9999 }
                                Text { text: "Y:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                                SpinBox { id: spinRy; Layout.preferredWidth: 55; from: 0; to: 9999 }
                                Text { text: "W:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                                SpinBox { id: spinRw; Layout.preferredWidth: 55; from: 0; to: 9999; value: 200 }
                                Text { text: "H:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                                SpinBox { id: spinRh; Layout.preferredWidth: 55; from: 0; to: 9999; value: 100 }
                            }

                            RowLayout {
                                spacing: 4
                                Button {
                                    text: "粘贴"
                                    implicitHeight: 26
                                    contentItem: Text {
                                        text: parent.text
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.textPrimary
                                        horizontalAlignment: Text.AlignHCenter
                                        verticalAlignment: Text.AlignVCenter
                                    }
                                    background: Rectangle { color: Theme.bgTrack; radius: 4 }
                                }
                                Item { Layout.fillWidth: true }
                            }
                        }
                    }
                }
            }

            // ---- 检测条件列表 ----
            GroupBox {
                title: "检测条件列表"
                Layout.fillWidth: true
                background: Rectangle {
                    color: Theme.bgSecondary
                    radius: Theme.radius
                    border.color: Theme.border
                }
                label: Text {
                    text: "检测条件列表（全部匹配才算通过）"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                    color: Theme.textPrimary
                    x: parent.leftPadding
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4

                    ListView {
                        id: conditionList
                        Layout.fillWidth: true
                        Layout.preferredHeight: 100
                        model: ListModel { id: conditionModel }
                        clip: true

                        delegate: Rectangle {
                            width: conditionList.width
                            height: 28
                            color: index % 2 === 0 ? Theme.accentOverlay6 : "transparent"
                            radius: 2
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 8
                                text: templateName + " (阈值: " + threshold + ")"
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: Theme.textPrimary
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: conditionList.currentIndex = index
                            }
                        }
                    }

                    RowLayout {
                        spacing: 4
                        Button {
                            text: "移除选中"
                            implicitHeight: 26
                            contentItem: Text {
                                text: parent.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: Theme.textPrimary
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle { color: Theme.bgTrack; radius: 4 }
                        }
                        Button {
                            text: "清空列表"
                            implicitHeight: 26
                            contentItem: Text {
                                text: parent.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: Theme.danger
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle { color: Theme.bgTrack; radius: 4 }
                        }
                        Item { Layout.fillWidth: true }
                    }
                }
            }

            // ---- 检测定位按钮 ----
            Button {
                text: "检测定位"
                Layout.fillWidth: true
                implicitHeight: 34
                contentItem: Text {
                    text: parent.text
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    font.bold: true
                    color: Theme.bgPrimary
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle { color: Theme.accent; radius: Theme.radius }
            }

            // ---- 注册区域 ----
            RowLayout {
                spacing: 4
                TextField {
                    id: registerNameInput
                    Layout.fillWidth: true
                    placeholderText: "注册名称（留空用文件名）"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textPrimary
                    background: Rectangle {
                        color: Theme.bgTrack
                        radius: 4
                        border.color: Theme.border
                    }
                }
                Button {
                    text: "注册区域"
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: Theme.bgTrack; radius: Theme.radius }
                }
            }
        }
    }
}