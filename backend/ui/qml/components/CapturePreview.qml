import QtQuick
import QtQuick.Layouts
import GenshinUI

Rectangle {
    id: root

    color: Theme.bgTrack
    border.color: Theme.border
    radius: Theme.radius
    implicitHeight: 150
    implicitWidth: 200

    // ---- 公开属性 ----
    property url source: ""          // 图片源
    property string infoText: "等待截图…" // 底部信息
    property bool selectionMode: false   // 选区模式
    property real zoomFactor: 1.0
    property bool fitToView: true

    // ---- 信号 ----
    signal regionSelected(int x, int y, int w, int h)
    signal clearRequested()

    // ---- 缩放函数 ----
    function zoomIn() {
        root.fitToView = false;
        root.zoomFactor = Math.min(root.zoomFactor + 0.25, 5.0);
    }
    function zoomOut() {
        root.fitToView = false;
        root.zoomFactor = Math.max(root.zoomFactor - 0.25, 0.25);
    }
    function zoomFit() {
        root.fitToView = true;
        root.zoomFactor = 1.0;
    }
    function clear() {
        root.source = "";
        root.infoText = "等待截图…";
    }

    // 统一设置预览图：保存当前滚动位置，设新 URL 后等待 Image 加载完成再恢复
    function displayImage(key, text) {
        scrollRestoreTimer.cx = flickable.contentX;
        scrollRestoreTimer.cy = flickable.contentY;
        root.source = "image://preview/" + key;
        root.infoText = text;
    }

    Timer {
        id: scrollRestoreTimer
        interval: 0
        repeat: false
        property real cx: 0
        property real cy: 0
        onTriggered: {
            flickable.contentX = cx;
            flickable.contentY = cy;
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ---- 工具栏 ----
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 6
            spacing: 4

            Item {
                Layout.fillWidth: true
            }

            GButton {
                text: "-"
                implicitWidth: 30
                implicitHeight: 30
                colorType: "default"
                onClicked: root.zoomOut()
            }

            Text {
                text: root.fitToView ? "适应" : Math.round(root.zoomFactor * 100) + "%"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                Layout.preferredWidth: 40
                horizontalAlignment: Text.AlignHCenter
            }

            GButton {
                text: "+"
                implicitWidth: 30
                implicitHeight: 30
                colorType: "default"
                onClicked: root.zoomIn()
            }

            GButton {
                text: "适应"
                colorType: "info"
                onClicked: root.zoomFit()
            }

            GButton {
                text: "全屏"
                colorType: "primary"
                visible: root.source !== null && root.source.toString() !== ""
                onClicked: fullscreenPreview.open()
            }

            GButton {
                text: "清除"
                visible: root.source !== null && root.source.toString() !== ""
                colorType: "warning"
                onClicked: {
                    root.clear()
                    root.clearRequested()
                }
            }

            Text {
                text: root.infoText
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textMuted
                elide: Text.ElideRight
                Layout.maximumWidth: 200
            }
        }

        // ---- 图片预览区 ----
        Flickable {
            id: flickable
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: imageContainer.width
            contentHeight: imageContainer.height

            Rectangle {
                anchors.fill: parent
                color: Theme.bgPrimary
            }

            // Ctrl+滚轮缩放
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.NoButton
                onWheel: function (wheel) {
                    if (wheel.modifiers & Qt.ControlModifier) {
                        if (wheel.angleDelta.y > 0)
                            root.zoomIn();
                        else
                            root.zoomOut();
                    }
                }
            }

            Item {
                id: imageContainer
                width: root.fitToView ? flickable.width : Math.max(flickable.width, imageItem.width)
                height: root.fitToView ? flickable.height : Math.max(flickable.height, imageItem.height)

                Image {
                    id: imageItem
                    anchors.centerIn: parent
                    source: root.source
                    visible: root.source !== null && root.source.toString() !== ""
                    fillMode: Image.PreserveAspectFit
                    width: root.fitToView ? flickable.width : implicitWidth * root.zoomFactor
                    height: root.fitToView ? flickable.height : implicitHeight * root.zoomFactor

                    onStatusChanged: {
                        if (status === Image.Ready)
                            scrollRestoreTimer.start()
                    }

                    // 选区拖拽
                    MouseArea {
                        anchors.fill: parent
                        enabled: root.selectionMode
                        cursorShape: enabled ? Qt.CrossCursor : Qt.ArrowCursor
                        preventStealing: true

                        property point startPoint
                        property bool dragging: false

                        onPressed: function (mouse) {
                            startPoint = Qt.point(mouse.x, mouse.y);
                            dragging = true;
                            rubberBand.x = mouse.x;
                            rubberBand.y = mouse.y;
                            rubberBand.width = 0;
                            rubberBand.height = 0;
                            rubberBand.visible = true;
                        }
                        onPositionChanged: function (mouse) {
                            if (!dragging)
                                return;
                            let x = Math.min(startPoint.x, mouse.x);
                            let y = Math.min(startPoint.y, mouse.y);
                            let w = Math.abs(mouse.x - startPoint.x);
                            let h = Math.abs(mouse.y - startPoint.y);
                            rubberBand.x = x;
                            rubberBand.y = y;
                            rubberBand.width = w;
                            rubberBand.height = h;
                        }
                        onReleased: function (mouse) {
                            dragging = false;
                            rubberBand.visible = false;
                            let sx = Math.min(startPoint.x, mouse.x);
                            let sy = Math.min(startPoint.y, mouse.y);
                            let sw = Math.abs(mouse.x - startPoint.x);
                            let sh = Math.abs(mouse.y - startPoint.y);
                            if (sw > 5 && sh > 5) {
                                // 使用 paintedWidth/paintedHeight 获取 PreserveAspectFit 下的实际渲染区域
                                let pw = imageItem.paintedWidth;
                                let ph = imageItem.paintedHeight;
                                let ox = (imageItem.width - pw) / 2;
                                let oy = (imageItem.height - ph) / 2;
                                // 映射回原始图像坐标
                                let scaleX = imageItem.implicitWidth / pw;
                                let scaleY = imageItem.implicitHeight / ph;
                                let imgX = Math.round((sx - ox) * scaleX);
                                let imgY = Math.round((sy - oy) * scaleY);
                                let imgW = Math.round(sw * scaleX);
                                let imgH = Math.round(sh * scaleY);
                                console.log("CapturePreview: regionSelected",
                                    "display=(" + sx + "," + sy + "," + sw + "x" + sh + ")",
                                    "painted=(" + pw + "x" + ph + ") offset=(" + ox + "," + oy + ")",
                                    "scale=(" + scaleX + "," + scaleY + ")",
                                    "image=(" + imgX + "," + imgY + "," + imgW + "x" + imgH + ")");
                                root.regionSelected(imgX, imgY, imgW, imgH);
                            }
                        }
                    }

                    // 选区框
                    Rectangle {
                        id: rubberBand
                        visible: false
                        color: "#0F00FF00"
                        border.color: "#00FF00"
                        border.width: 2
                    }
                }

                // 无图片时的占位文字
                Text {
                    anchors.centerIn: parent
                    visible: !imageItem.visible
                    text: "未开始预览\n点击「开始预览」查看游戏画面"
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    color: Theme.textMuted
                    horizontalAlignment: Text.AlignHCenter
                }
            }
        }
    }

    // ---- 全屏预览 ----
    FullscreenPreview {
        id: fullscreenPreview
        source: root.source
    }
}