import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// 卡片容器：等价于 Vue 的 el-card，标题 + 默认插槽
// 使用 default property alias 将子组件重定向到卡片内容区
Pane {
    id: control

    // ============================================================
    // 公开属性
    // ============================================================
    property string title: ""
    property string subtitle: ""

    // 默认插槽：GCard { } 内的子组件自动放入 contentSlot
    // 等价于 Vue 的 <slot />
    // 注意：不能命名为 contentChildren，Pane 基类已有同名的 FINAL 属性
    default property alias cardContent: contentSlot.data

    padding: 12

    // ============================================================
    // 背景
    // ============================================================
    background: Rectangle {
        color: Theme.bgCard
        radius: Theme.radius
        border.color: Theme.border
    }

    // ============================================================
    // 内容区：标题 + 用户子元素插槽
    // ============================================================
    contentItem: ColumnLayout {
        spacing: 8

        // -- 标题 --
        Text {
            text: control.title
            font.family: Theme.fontFamily
            font.pixelSize: 14
            font.bold: true
            color: Theme.textPrimary
            visible: control.title !== ""
        }

        // -- 副标题 --
        Text {
            text: control.subtitle
            font.family: Theme.fontFamily
            font.pixelSize: 12
            color: Theme.textSecondary
            visible: control.subtitle !== ""
        }

        // -- 内容插槽（GCard 的子组件会出现在这里）--
        ColumnLayout {
            id: contentSlot
            Layout.fillWidth: true
            spacing: 8
        }
    }
}