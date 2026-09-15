import QtQuick
import GenshinUI


Canvas {
    id: root

    // ---- 可定制属性 ----
    property string watermarkText: "内部开发版本，不代表最终品质"
    property string subText: "" // 副标题（如版本号），为空则不显示
    property int fontSize: 12
    property int subFontSize: 10
    property string textColor: "rgba(255, 80, 80, 0.10)"
    property real watermarkRotation: -25
    property int rowSpacing: 130
    property int colSpacing: 380

    anchors.fill: parent
    z: 9999
    enabled: false

    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    onPaint: {
        var ctx = getContext("2d");
        ctx.clearRect(0, 0, width, height);
        ctx.save();

        ctx.translate(width / 2, height / 2);
        ctx.rotate(watermarkRotation * Math.PI / 180);
        ctx.textAlign = "center";
        ctx.fillStyle = textColor;

        var cols = Math.ceil(width / colSpacing) + 2;
        var rows = Math.ceil(height / rowSpacing) + 2;

        for (let row = -rows; row < rows; row++) {
            for (let col = -cols; col < cols; col++) {
                let x = col * colSpacing;
                let y = row * rowSpacing;

                // 主文字
                ctx.font = fontSize + "px '" + Theme.fontFamily + "'";
                ctx.fillText(watermarkText, x, y);

                // 副文字（版本号等）
                if (subText !== "") {
                    ctx.font = subFontSize + "px '" + Theme.fontFamily + "'";
                    ctx.fillText(subText, x, y + fontSize + 4);
                }
            }
        }

        ctx.restore();
    }
}