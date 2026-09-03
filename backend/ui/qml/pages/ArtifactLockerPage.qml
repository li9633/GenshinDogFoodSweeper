import QtQuick
import QtQuick.Layouts
import GenshinUI
import "../components"
// qmllint disable unqualified

Rectangle {
    id: root
    property string pageTitle: "圣遗物锁定器"
    color: Theme.bgPrimary

    property var _selectedNames: []

    Component.onCompleted: {
        ArtifactLocker.reloadRules();
        _selectedNames = ArtifactLocker.selectedRuleNames;
    }

    Connections {
        target: ArtifactLocker
        function onSelectedRuleNamesChanged() {
            _selectedNames = ArtifactLocker.selectedRuleNames;
        }
    }

    function _toggleSelect(name) {
        ArtifactLocker.toggleRuleSelection(name);
    }

    function _isSelected(name) {
        return _selectedNames.indexOf(name) >= 0;
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ==== 规则列表 ====
        Text {
            text: "选择规则（最多 " + ArtifactLocker.maxRuleSelection + " 条）"
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
            model: ArtifactLocker.rules

            delegate: RuleCard {
                width: ruleList.width
                ruleData: modelData
                rightClickEnabled: false
                highlighted: _isSelected(modelData.name)
                onClicked: function(rule) { _toggleSelect(rule.name) }
            }

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
                model: ArtifactLocker.defaultActionLabels
                currentIndex: ArtifactLocker.defaultActionIndex
                enabled: !ArtifactLocker.running
                onActivated: (index) => ArtifactLocker.selectDefaultAction(index)
            }

            GCheckBox {
                text: "跳过已锁定的圣遗物"
                checked: !ArtifactLocker.reUnlock
                enabled: !ArtifactLocker.running
                onCheckedChanged: ArtifactLocker.setReUnlock(!checked)
            }

            GCheckBox {
                text: "限制处理数量"
                checked: ArtifactLocker.limitCountEnabled
                enabled: !ArtifactLocker.running
                onCheckedChanged: ArtifactLocker.setLimitCountEnabled(checked)
            }

            GSpinBox {
                from: 1
                to: 9999
                value: ArtifactLocker.maxCount
                editable: true
                implicitWidth: 70
                implicitHeight: 32
                enabled: ArtifactLocker.limitCountEnabled && !ArtifactLocker.running
                visible: ArtifactLocker.limitCountEnabled
                onValueChanged: ArtifactLocker.setMaxCount(value)
            }

            Text {
                visible: ArtifactLocker.limitCountEnabled
                text: "个"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }

            Item { Layout.fillWidth: true }

            // 统计信息
            ColumnLayout {
                visible: ArtifactLocker.lockedCount > 0 || ArtifactLocker.unlockedCount > 0
                spacing: 2

                Text {
                    text: "锁定: " + ArtifactLocker.lockedCount + " | 解锁: " + ArtifactLocker.unlockedCount + " | 跳过: " + ArtifactLocker.skippedCount
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textSecondary
                }

                Text {
                    text: ArtifactLocker.status || ""
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                    visible: text !== ""
                }
            }

            Text {
                text: ArtifactLocker.status || ""
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                visible: text !== "" && (ArtifactLocker.lockedCount === 0 && ArtifactLocker.unlockedCount === 0)
                Layout.rightMargin: 8
            }

            GButton {
                text: ArtifactLocker.running ? "锁定中..." : "开始锁定"
                colorType: "primary"
                enabled: !ArtifactLocker.running && _selectedNames.length > 0
                onClicked: ArtifactLocker.startLock()
            }

            GButton {
                visible: ArtifactLocker.running
                text: "停止"
                colorType: "danger"
                onClicked: ArtifactLocker.stopLock()
            }
        }
    }
}