import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified
// ElementDetection 是 Python 通过 setContextProperty 注入的上下文属性，qmllint 无法识别

Rectangle {
    id: root
    color: "transparent"
    Layout.fillWidth: true
    Layout.fillHeight: true

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 8
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 6

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
                    // qmllint disable missing-property
                    x: parent.leftPadding
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4

                    // 搜索 + 刷新
                    RowLayout {
                        spacing: 3
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
                            onTextChanged: searchTimer.restart()
                        }
                        Timer {
                            id: searchTimer
                            interval: 300
                            onTriggered: ElementDetection.searchTemplates(searchInput.text)
                        }
                        Button {
                            text: "⟳"
                            implicitWidth: 28; implicitHeight: 28
                            contentItem: Text {
                                // qmllint disable missing-property
                                text: parent.text
                                font.family: Theme.fontFamily
                                font.pixelSize: 14
                                color: Theme.textPrimary
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                            background: Rectangle { color: Theme.bgTrack; radius: 4 }
                            onClicked: ElementDetection.reloadTemplates()
                        }
                    }

                    // 模板 + 阈值 + 添加
                    RowLayout {
                        spacing: 4
                        Text { text: "模板:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                        ComboBox {
                            id: templateCombo
                            Layout.fillWidth: true
                            model: ElementDetection.templateList
                            textRole: "displayText"
                            valueRole: "name"
                            currentIndex: -1
                            displayText: currentIndex >= 0 ? currentText : "请选择模板…"
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
                            onActivated: ElementDetection.selectTemplate(templateCombo.currentValue)
                        }
                        Text { text: "阈值:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                        GSpinBox {
                            id: spinThreshold
                            Layout.preferredWidth: 70
                            from: 0; to: 100
                            value: 80
                            editable: true
                        }
                        GButton {
                            text: "+ 添加"
                            colorType: "primary"
                            enabled: templateCombo.currentIndex >= 0
                            onClicked: ElementDetection.addConditionByIndex(
                                templateCombo.currentIndex,
                                spinThreshold.value,
                                chkRegion.checked,
                                spinRx.value, spinRy.value, spinRw.value, spinRh.value
                            )
                        }
                    }

                    // 预览 + 限定区域
                    RowLayout {
                        spacing: 4

                        Rectangle {
                            width: 100; height: 80
                            color: "#2b2b2b"
                            border.color: Theme.border
                            radius: 2
                            Image {
                                id: templatePreview
                                anchors.fill: parent
                                anchors.margins: 2
                                fillMode: Image.PreserveAspectFit
                                visible: source !== ""
                            }
                            Text {
                                anchors.centerIn: parent
                                text: "无预览"
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: "#888"
                                visible: templatePreview.source === ""
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3

                            RowLayout {
                                spacing: 2
                                GCheckBox {
                                    id: chkRegion
                                    text: "限定区域"
                                }
                                Text { text: "X:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                                GSpinBox { id: spinRx; Layout.preferredWidth: 55; from: 0; to: 9999 }
                                Text { text: "Y:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                                GSpinBox { id: spinRy; Layout.preferredWidth: 55; from: 0; to: 9999 }
                                Text { text: "W:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                                GSpinBox { id: spinRw; Layout.preferredWidth: 55; from: 0; to: 9999; value: 200 }
                                Text { text: "H:"; font.family: Theme.fontFamily; font.pixelSize: 12; color: Theme.textSecondary }
                                GSpinBox { id: spinRh; Layout.preferredWidth: 55; from: 0; to: 9999; value: 100 }
                            }

                            RowLayout {
                                spacing: 4
                                GButton {
                                        text: "粘贴"
                                        colorType: "default"
                                        implicitHeight: 26
                                        onClicked: {
                                            var parts = Clipboard.text().split(",")
                                            if (parts.length >= 4) {
                                                spinRx.value = parseInt(parts[0]) || 0
                                                spinRy.value = parseInt(parts[1]) || 0
                                                spinRw.value = parseInt(parts[2]) || 0
                                                spinRh.value = parseInt(parts[3]) || 0
                                                chkRegion.checked = true
                                            }
                                        }
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
                    // qmllint disable missing-property
                    x: parent.leftPadding
                }

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 4

                    ListView {
                        id: conditionList
                        Layout.fillWidth: true
                        Layout.preferredHeight: 100
                        model: ElementDetection.conditions
                        clip: true

                        delegate: Rectangle {
                            required property int index
                            required property var modelData

                            width: conditionList.width
                            height: 28
                            color: index % 2 === 0 ? Theme.accentOverlay6 : "transparent"
                            radius: 2
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 8
                                text: modelData.templateName + "(" + modelData.fileName + ")（" + modelData.thresholdText + "，" + modelData.regionText + "）"
                                font.family: Theme.fontFamily
                                font.pixelSize: 12
                                color: Theme.textPrimary
                                elide: Text.ElideRight
                                width: parent.width - 16
                            }
                            MouseArea {
                                anchors.fill: parent
                                onClicked: conditionList.currentIndex = index
                            }
                        }
                    }

                    RowLayout {
                        spacing: 4
                        GButton {
                            text: "移除选中"
                            colorType: "default"
                            implicitHeight: 26
                            onClicked: {
                                if (conditionList.currentIndex >= 0) {
                                    ElementDetection.removeCondition(conditionList.currentIndex)
                                }
                            }
                        }
                        GButton {
                            text: "清空列表"
                            colorType: "danger"
                            implicitHeight: 26
                            onClicked: ElementDetection.clearConditions()
                        }
                        Item { Layout.fillWidth: true }
                    }
                }
            }

            // ---- 检测定位按钮 ----
            GButton {
                id: btnDetect
                text: ElementDetection.detecting ? "检测中…" : "检测定位"
                colorType: "primary"
                enabled: ElementDetection.conditionCount > 0 && !ElementDetection.detecting
                Layout.fillWidth: true
                implicitHeight: 34
                onClicked: {
                    ElementDetection.detect()
                }
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
                GButton {
                    text: "注册区域"
                    colorType: "default"
                    implicitHeight: 30
                    onClicked: {
                        if (conditionList.currentIndex >= 0) {
                            ElementDetection.registerRegionByIndex(conditionList.currentIndex, registerNameInput.text)
                        }
                    }
                }
            }

            // ---- 检测结果 ----
            Text {
                id: detectionResult
                Layout.fillWidth: true
                text: ""
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textSecondary
                wrapMode: Text.WordWrap
                visible: text !== ""
            }

            Item { Layout.fillHeight: true }
        }
    }

    // ============================================================
    // Presenter 信号连接
    // ============================================================
    Connections {
        target: ElementDetection

        function onTemplateSelected(key, previewPath, rx, ry, rw, rh, hasRegion) {
            templatePreview.source = previewPath ? "file:///" + previewPath : ""
            if (hasRegion) {
                spinRx.value = rx
                spinRy.value = ry
                spinRw.value = rw
                spinRh.value = rh
                chkRegion.checked = true
            }
        }

        function onDetectionFinished(allPassed, detailText, resultPath) {
            detectionResult.text = detailText
        }

        function onRegionRegistered(name, x, y, w, h) {
            registerNameInput.text = ""
        }

        function onErrorOccurred(msg) {
            detectionResult.text = "错误: " + msg
        }
    }

}