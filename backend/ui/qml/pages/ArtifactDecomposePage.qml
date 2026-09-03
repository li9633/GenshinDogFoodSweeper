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
        ArtifactDecompose.reloadRules();
        _selectedNames = ArtifactDecompose.selectedRuleNames;
    }

    Connections {
        target: ArtifactDecompose
        function onSelectedRuleNamesChanged() {
            _selectedNames = ArtifactDecompose.selectedRuleNames;
        }
    }

    function _toggleSelect(name) {
        ArtifactDecompose.toggleRuleSelection(name);
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
            text: "选择规则（最多 " + ArtifactDecompose.maxRuleSelection + " 条）"
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
            model: ArtifactDecompose.rules

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
                model: ArtifactDecompose.defaultActionLabels
                currentIndex: ArtifactDecompose.defaultActionIndex
                enabled: !ArtifactDecompose.running
                onActivated: (index) => ArtifactDecompose.selectDefaultAction(index)
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
                value: ArtifactDecompose.maxDiscardCount
                editable: true
                implicitWidth: 80
                implicitHeight: 32
                enabled: !ArtifactDecompose.running
                onValueChanged: ArtifactDecompose.setMaxDiscardCount(value)
            }

            Item { Layout.fillWidth: true }

            Text {
                text: ArtifactDecompose.status || ""
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                visible: text !== ""
                Layout.rightMargin: 8
            }

            // 选择前：开始分解按钮
            GButton {
                visible: !ArtifactDecompose.selectionDone
                text: ArtifactDecompose.running ? "选择中..." : "开始分解"
                colorType: "primary"
                enabled: !ArtifactDecompose.running && _selectedNames.length > 0
                onClicked: ArtifactDecompose.startDecompose()
            }

            // 选择后：确认 / 取消 按钮
            GButton {
                visible: ArtifactDecompose.selectionDone
                text: "取消"
                colorType: "default"
                onClicked: ArtifactDecompose.cancelDecompose()
            }

            GButton {
                visible: ArtifactDecompose.selectionDone
                text: "确认分解"
                colorType: "danger"
                enabled: ArtifactDecompose.pendingDiscard > 0
                onClicked: ArtifactDecompose.confirmDecompose()
            }
        }
    }
}