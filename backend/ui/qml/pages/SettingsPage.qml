import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI
import "../components"
import "settings"

// qmllint disable unqualified

Rectangle {
    id: root
    property string pageTitle: "设置"
    color: Theme.bgPrimary

    property int currentTab: 0

    // ============================================================
    // 布局：左侧 Tab 菜单 + 右侧内容区
    // ============================================================
    RowLayout {
        anchors.fill: parent
        spacing: 0

        // -- 左侧 Tab 菜单 --
        TabMenu {
            id: tabMenu
            Layout.fillHeight: true
            currentIndex: currentTab
            model: _tabItems
            onTabSelected: function(index) { currentTab = index }
        }

        // 分隔线
        Rectangle {
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            color: Theme.border
        }

        // -- 右侧内容区 --
        ScrollView {
            id: contentScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            StackLayout {
                width: contentScroll.width
                currentIndex: currentTab

                // ============================================
                // Tab 0: 通用
                // ============================================
                GeneralTab {}

                // ============================================
                // Tab 1: 外观
                // ============================================
                AppearanceTab {}

                // ============================================
                // Tab 2: 同步
                // ============================================
                SyncTab {}

                // ============================================
                // Tab 3: 模型
                // ============================================
                ModelTab {}

                // ============================================
                // Tab 4: 快捷键
                // ============================================
                HotkeyTab {}

                // ============================================
                // Tab 5: 关于
                // ============================================
                AboutTab {}
            }
        }
    }

    // ============================================================
    // Tab 数据模型
    // ============================================================
    readonly property var _tabItems: [
        { key: "general",    icon: Icon.sliders,      label: "通用" },
        { key: "appearance", icon: Icon.palette,       label: "外观" },
        { key: "sync",       icon: Icon.arrowsRotate,  label: "同步" },
        { key: "model",      icon: Icon.flask,         label: "模型" },
        { key: "hotkey",     icon: Icon.keyboard,      label: "快捷键" },
        { key: "about",      icon: Icon.info,          label: "关于" },
    ]

    function goToTab(key) {
        for (let i = 0; i < _tabItems.length; i++) {
            if (_tabItems[i].key === key) {
                currentTab = i;
                return;
            }
        }
    }
}