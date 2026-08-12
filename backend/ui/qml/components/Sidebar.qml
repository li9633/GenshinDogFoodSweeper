import QtQuick
import GenshinUI

// qmllint disable unqualified
// EnvManager 是 Python 上下文属性；Loader sourceComponent 内联组件中访问 root/model 是标准 Qt 写法

Rectangle {
    id: root

    width: 200
    color: Theme.bgSidebar

    property string currentKey: "dogfood"
    signal pageSelected(string key)

    // ============================================================
    // 菜单数据模型
    // ============================================================
    ListModel {
        id: menuModel
        ListElement { type: "section"; key: "launcher"; text: "启动"; icon: "🚀"; expanded: true }
        ListElement { type: "link";   key: "dogfood";  text: "狗粮清理器";   parentKey: "launcher"; indent: true }
        ListElement { type: "link";   key: "scanner";  text: "圣遗物扫描器"; parentKey: "launcher"; indent: true }
        ListElement { type: "link";   key: "locker";   text: "圣遗物锁定器"; parentKey: "launcher"; indent: true }
        ListElement { type: "link";   key: "rules";    text: "规则预设";     icon: "📋" }
        ListElement { type: "link";   key: "settings"; text: "设置";         icon: "⚙️" }
    }

    Component.onCompleted: {
        if (EnvManager.isDebug) {
            menuModel.append({ type: "link", key: "debug", text: "调试", icon: "🔧" })
        }
    }

    // ============================================================
    // 展开状态存储
    // ============================================================
    property var expandedSections: ({ "launcher": true })

    function toggleSection(key) {
        let map = {}
        for (let k in expandedSections) map[k] = expandedSections[k]
        map[key] = !map[key]
        expandedSections = map
    }

    // ============================================================
    // 列表
    // ============================================================
    ListView {
        anchors.fill: parent
        anchors.topMargin: 12
        spacing: 0
        model: menuModel
        interactive: false

        delegate: Item {
            width: root.width
            height: visible ? (model.type === "section" ? 44 : 40) : 0
            visible: {
                if (model.type === "section") return true
                if (model.indent === undefined || !model.indent) return true
                let pk = model.parentKey || ""
                return root.expandedSections[pk] === true
            }

            // -- 分组标题 --
            Loader {
                anchors.fill: parent
                active: model.type === "section"
                sourceComponent: Rectangle {
                    color: "transparent"

                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 20
                        spacing: 10

                        Text {
                            text: model.icon || ""
                            font.pixelSize: 14
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: model.text || ""
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: Theme.textPrimary
                            anchors.verticalCenter: parent.verticalCenter
                        }

                        Text {
                            text: root.expandedSections[model.key] ? "▼" : "▶"
                            font.pixelSize: 11
                            color: Theme.textMuted
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.toggleSection(model.key)
                    }
                }
            }

            // -- 子链接 --
            Loader {
                anchors.fill: parent
                active: model.type === "link"
                sourceComponent: Rectangle {
                    color: root.currentKey === model.key
                           ? Theme.accentOverlay10
                           : "transparent"

                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: model.indent ? 44 : 20
                        spacing: 10

                        Text {
                            text: model.icon || ""
                            font.pixelSize: 14
                            anchors.verticalCenter: parent.verticalCenter
                            visible: model.icon !== undefined && model.icon !== ""
                        }

                        Text {
                            text: model.text || ""
                            font.family: Theme.fontFamily
                            font.pixelSize: 14
                            color: root.currentKey === model.key
                                   ? Theme.accent
                                   : Theme.textSecondary
                            font.weight: root.currentKey === model.key
                                         ? Font.DemiBold
                                         : Font.Normal
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        hoverEnabled: true
                        onClicked: root.pageSelected(model.key)

                        Rectangle {
                            anchors.fill: parent
                            color: Theme.accentOverlay6
                            visible: parent.containsMouse
                                     && root.currentKey !== model.key
                        }
                    }
                }
            }
        }
    }
}