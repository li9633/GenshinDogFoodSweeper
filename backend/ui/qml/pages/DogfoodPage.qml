import QtQuick
import QtQuick.Layouts
import GenshinUI
import "../components"
// qmllint disable unqualified

Rectangle {
    id: root
    property string pageTitle: "狗粮清理器"
    color: Theme.bgPrimary

    // 多选状态（内部追踪，避免与 Presenter 双向绑定冲突）
    property var _selectedNames: []

    Component.onCompleted: {
        DogfoodPresenter.reloadRules();
        _selectedNames = DogfoodPresenter.selectedRuleNames;
    }

    Connections {
        target: DogfoodPresenter
        function onSelectedRuleNamesChanged() {
            _selectedNames = DogfoodPresenter.selectedRuleNames;
        }
    }

    function _toggleSelect(name) {
        DogfoodPresenter.toggleRuleSelection(name);
    }

    function _isSelected(name) {
        return _selectedNames.indexOf(name) >= 0;
    }

    // ============================================================
    // 主布局
    // ============================================================
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ==== 规则列表 ====
        Text {
            text: "选择规则（最多 " + DogfoodPresenter.maxRuleSelection + " 条）"
            font.family: Theme.fontFamily
            font.pixelSize: 14
            color: Theme.textPrimary
        }

        ListView {
            id: ruleList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 6
            model: DogfoodPresenter.rules

            delegate: RuleCard {
                width: ruleList.width
                ruleData: modelData
                rightClickEnabled: false
                highlighted: _isSelected(modelData.name)
                onClicked: function(rule) { _toggleSelect(rule.name) }
            }

            // 空状态提示
            Rectangle {
                anchors.fill: parent
                color: "transparent"
                visible: ruleList.count === 0

                Text {
                    anchors.centerIn: parent
                    text: "暂无规则，请先在「规则预设」页面创建规则"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textMuted
                }
            }
        }

        // ==== 底部操作栏 ====
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Text {
                text: "未命中时默认:"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }

            GComboBox {
                implicitWidth: 80
                model: DogfoodPresenter.defaultActionLabels
                currentIndex: DogfoodPresenter.defaultActionIndex
                enabled: !DogfoodPresenter.running
                onActivated: DogfoodPresenter.selectDefaultAction(index)
            }

            Text {
                text: "每批最多:"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }

            GSpinBox {
                id: maxDiscardSpin
                from: 1
                to: 1000
                value: DogfoodPresenter.maxDiscardCount
                editable: true
                implicitWidth: 80
                implicitHeight: 32
                enabled: !DogfoodPresenter.running
                onValueChanged: DogfoodPresenter.setMaxDiscardCount(value)
            }

            Item { Layout.fillWidth: true }

            Text {
                text: DogfoodPresenter.status || ""
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                visible: text !== ""
                Layout.rightMargin: 8
            }

            // 选择前：开始分解按钮
            GButton {
                visible: !DogfoodPresenter.selectionDone
                text: DogfoodPresenter.running ? "选择中..." : "开始分解"
                colorType: "primary"
                enabled: !DogfoodPresenter.running && _selectedNames.length > 0
                onClicked: DogfoodPresenter.startDecompose()
            }

            // 选择后：确认 / 取消 按钮
            GButton {
                visible: DogfoodPresenter.selectionDone
                text: "取消"
                colorType: "default"
                onClicked: DogfoodPresenter.cancelDecompose()
            }

            GButton {
                visible: DogfoodPresenter.selectionDone
                text: "确认分解"
                colorType: "danger"
                enabled: DogfoodPresenter.pendingDiscard > 0
                onClicked: DogfoodPresenter.confirmDecompose()
            }
        }
    }
}