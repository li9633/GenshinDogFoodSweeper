import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

Rectangle {
    id: root
    color: "transparent"
    Layout.fillWidth: true
    Layout.fillHeight: true

    property bool marking: false
    property bool extracting: false

    // 坐标变更 → 同步到 Presenter
    function syncCoords() {
        RegionMarker.setCoords(spinX.value, spinY.value, spinW.value, spinH.value)
    }

    ScrollView {
        id: scrollView
        anchors.fill: parent
        anchors.margins: 12
        clip: true

        ColumnLayout {
            width: scrollView.availableWidth
            spacing: 10

            // ---- 坐标输入 ----
            RowLayout {
                spacing: 6

                Text { text: "X:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                SpinBox { id: spinX; Layout.preferredWidth: 70; from: 0; to: 9999; value: 0; onValueChanged: syncCoords() }

                Text { text: "Y:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                SpinBox { id: spinY; Layout.preferredWidth: 70; from: 0; to: 9999; value: 0; onValueChanged: syncCoords() }

                Text { text: "宽:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                SpinBox { id: spinW; Layout.preferredWidth: 70; from: 1; to: 9999; value: 100; onValueChanged: syncCoords() }

                Text { text: "高:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                SpinBox { id: spinH; Layout.preferredWidth: 70; from: 1; to: 9999; value: 100; onValueChanged: syncCoords() }
            }

            // ---- 保存模板 ----
            RowLayout {
                spacing: 6

                Text { text: "文件名:"; font.family: Theme.fontFamily; font.pixelSize: 13; color: Theme.textSecondary }
                TextField {
                    id: filenameInput
                    Layout.fillWidth: true
                    placeholderText: "输入模板名称，如 圣遗物文本"
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
                    text: "保存为模板"
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
                    onClicked: {
                        if (filenameInput.text.trim() === "") {
                            console.log("[RegionMarker] 请输入文件名")
                            return
                        }
                        RegionMarker.saveTemplate(filenameInput.text)
                    }
                }
            }

            // ---- 操作按钮 ----
            RowLayout {
                spacing: 6

                Button {
                    id: btnMark
                    text: marking ? "截图中…" : "截图并标记"
                    enabled: !marking
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: parent.enabled ? Theme.bgPrimary : Theme.textMuted
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: parent.enabled ? Theme.accent : Theme.bgTrack; radius: Theme.radius }
                    onClicked: {
                        marking = true
                        RegionMarker.mark()
                    }
                }

                Button {
                    id: btnSelect
                    checkable: true
                    checked: RegionMarker.selectionMode
                    text: checked ? "选区中…" : "选区模式"
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: parent.checked ? Theme.bgPrimary : Theme.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        color: parent.checked ? Theme.accent : Theme.bgTrack
                        radius: Theme.radius
                    }
                    onToggled: {
                        RegionMarker.selectionMode = checked
                    }
                }

                Button {
                    text: "复制坐标"
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
                    onClicked: {
                        RegionMarker.copyCoords()
                        var coords = spinX.value + "," + spinY.value + "," + spinW.value + "," + spinH.value
                        Clipboard.setText(coords)
                        console.log("[RegionMarker] 已复制坐标: " + coords)
                    }
                }

                Button {
                    text: "清除"
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
                    onClicked: RegionMarker.clear()
                }

                Item { Layout.fillWidth: true }
            }

            // ---- 颜色提取 ----
            RowLayout {
                spacing: 8

                Button {
                    id: btnColor
                    text: extracting ? "提取中…" : "提取颜色"
                    enabled: !extracting
                    implicitHeight: 30
                    contentItem: Text {
                        text: parent.text
                        font.family: Theme.fontFamily
                        font.pixelSize: 12
                        color: parent.enabled ? Theme.bgPrimary : Theme.textMuted
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle { color: parent.enabled ? Theme.accent : Theme.bgTrack; radius: Theme.radius }
                    onClicked: {
                        extracting = true
                        RegionMarker.extractColor()
                    }
                }

                Rectangle {
                    id: colorSwatch
                    width: 24; height: 24
                    color: "#333333"
                    border.color: Theme.border
                    radius: 2
                }

                Text {
                    id: colorInfo
                    text: "点击按钮提取区域颜色"
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textSecondary
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    // ============================================================
    // Presenter 信号连接
    // ============================================================
    Connections {
        target: RegionMarker

        function onCaptureFinished(path, x, y, w, h) {
            marking = false
            console.log("[RegionMarker] 截图完成: " + path + " (" + x + "," + y + "," + w + "x" + h + ")")
        }

        function onColorExtracted(r, g, b, h, s, v) {
            extracting = false
            colorSwatch.color = Qt.rgba(r / 255, g / 255, b / 255, 1)
        }

        function onColorExtractedString(text) {
            colorInfo.text = text
        }

        function onTemplateSaved(filename) {
            console.log("[RegionMarker] 模板已保存: " + filename)
            filenameInput.text = ""
        }

        function onErrorOccurred(msg) {
            marking = false
            extracting = false
            console.log("[RegionMarker] 错误: " + msg)
        }

        function onCoordsChanged() {
            spinX.value = RegionMarker.regionX
            spinY.value = RegionMarker.regionY
            spinW.value = RegionMarker.regionW
            spinH.value = RegionMarker.regionH
        }
    }

    // 初始化坐标
    Component.onCompleted: syncCoords()
}