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
        LockerPresenter.reloadRules();
        _selectedNames = LockerPresenter.selectedRuleNames;
    }

    Connections {
        target: LockerPresenter
        function onSelectedRuleNamesChanged() {
            _selectedNames = LockerPresenter.selectedRuleNames;
        }
    }

    function _toggleSelect(name) {
        LockerPresenter.toggleRuleSelection(name);
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
            text: "选择规则（最多 " + LockerPresenter.maxRuleSelection + " 条）"
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
            model: LockerPresenter.rules

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
                model: LockerPresenter.defaultActionLabels
                currentIndex: LockerPresenter.defaultActionIndex
                enabled: !LockerPresenter.running
                onActivated: LockerPresenter.selectDefaultAction(index)
            }

            GCheckBox {
                text: "跳过已锁定的圣遗物"
                checked: !LockerPresenter.reUnlock
                enabled: !LockerPresenter.running
                onCheckedChanged: LockerPresenter.setReUnlock(!checked)
            }

            GCheckBox {
                text: "限制处理数量"
                checked: LockerPresenter.limitCountEnabled
                enabled: !LockerPresenter.running
                onCheckedChanged: LockerPresenter.setLimitCountEnabled(checked)
            }

            GSpinBox {
                from: 1
                to: 9999
                value: LockerPresenter.maxCount
                editable: true
                implicitWidth: 70
                implicitHeight: 32
                enabled: LockerPresenter.limitCountEnabled && !LockerPresenter.running
                visible: LockerPresenter.limitCountEnabled
                onValueChanged: LockerPresenter.setMaxCount(value)
            }

            Text {
                visible: LockerPresenter.limitCountEnabled
                text: "个"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }

            Item { Layout.fillWidth: true }

            // 统计信息
            ColumnLayout {
                visible: LockerPresenter.lockedCount > 0 || LockerPresenter.unlockedCount > 0
                spacing: 2

                Text {
                    text: "锁定: " + LockerPresenter.lockedCount + " | 解锁: " + LockerPresenter.unlockedCount + " | 跳过: " + LockerPresenter.skippedCount
                    font.family: Theme.fontFamily
                    font.pixelSize: 12
                    color: Theme.textSecondary
                }

                Text {
                    text: LockerPresenter.status || ""
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                    visible: text !== ""
                }
            }

            Text {
                text: LockerPresenter.status || ""
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                visible: text !== "" && (LockerPresenter.lockedCount === 0 && LockerPresenter.unlockedCount === 0)
                Layout.rightMargin: 8
            }

            GButton {
                text: LockerPresenter.running ? "锁定中..." : "开始锁定"
                colorType: "primary"
                enabled: !LockerPresenter.running && _selectedNames.length > 0
                onClicked: LockerPresenter.startLock()
            }

            GButton {
                visible: LockerPresenter.running
                text: "停止"
                colorType: "danger"
                onClicked: LockerPresenter.stopLock()
            }
        }
    }
}