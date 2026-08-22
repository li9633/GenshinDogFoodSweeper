import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import GenshinUI
import "../components"
// qmllint disable unqualified

Rectangle {
    id: root
    property string pageTitle: "规则预设"
    color: Theme.bgPrimary

    Component.onCompleted: {
        _updateVisibility();
    }

    function _updateVisibility() {
        const empty = RulePresenter.rules.length === 0;
        emptyHint.visible = empty;
        ruleList.visible = !empty;
    }

    Connections {
        target: RulePresenter
        function onRulesChanged() { _updateVisibility(); }
    }

    // 多选状态
    property var _selected: ({})

    function _toggleSelect(name) {
        let s = _selected;
        if (s[name]) {
            const copy = {};
            for (let k in s) if (k !== name) copy[k] = true;
            _selected = copy;
        } else {
            const copy2 = {};
            for (let k2 in s) copy2[k2] = true;
            copy2[name] = true;
            _selected = copy2;
        }
    }

    function _selectedCount() {
        return Object.keys(_selected).length;
    }

    function _selectedNames() {
        return Object.keys(_selected);
    }

    function _clearSelection() {
        _selected = ({});
    }

    // ============================================================
    // 主布局：不使用 ScrollView 包装，避免 Layout.fillHeight 失效
    // ============================================================
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // ==== 工具栏 ====
        RowLayout {
            Layout.fillWidth: true

            // 检测配置选择
            Text {
                text: "检测配置:"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }
            GComboBox {
                id: configCombo
                implicitWidth: 160
                model: RulePresenter.availableSlotConfigs
                textRole: "name"
                currentIndex: RulePresenter.selectedSlotConfigIndex
                onActivated: function(idx) {
                    RulePresenter.setSelectedSlotConfigIndex(idx);
                }
            }

            GButton {
                text: "测试当前圣遗物"
                colorType: "success"
                onClicked: {
                    RulePresenter.testCurrentArtifact();
                }
            }

            Text {
                id: testStatusText
                text: ""
                font.family: Theme.fontFamily
                font.pixelSize: 12
                color: Theme.textMuted
                visible: text !== ""
            }

            Item { Layout.fillWidth: true }

            GButton {
                text: "新建规则"
                colorType: "primary"
                onClicked: {
                    editDialog.editRule = ({});
                    editDialog.open();
                }
            }
            GButton {
                text: "导入"
                colorType: "info"
                onClicked: fileImportDialog.open()
            }
            GButton {
                visible: _selectedCount() > 0
                text: "导出选中(" + _selectedCount() + ")"
                colorType: "warning"
                onClicked: fileExportSelectedDialog.open()
            }

            Item { Layout.preferredWidth: 16 }

            Text {
                text: "未命中时:"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
            }
            GComboBox {
                implicitWidth: 80
                model: ["保留", "分解"]
                currentIndex: RulePresenter.defaultAction === "discard" ? 1 : 0
                onActivated: function(idx) {
                    RulePresenter.setDefaultAction(idx === 1 ? "discard" : "keep");
                }
            }
        }

        // ==== 规则列表区域 ====
        Item {
            id: listArea
            Layout.fillWidth: true
            Layout.fillHeight: true

            Text {
                id: emptyHint
                anchors.centerIn: parent
                text: "没有任何规则，请先创建一个规则"
                font.family: Theme.fontFamily
                font.pixelSize: 14
                color: Theme.textMuted
            }

            ListView {
                id: ruleList
                anchors.fill: parent
                clip: true
                model: RulePresenter.rules
                spacing: 8
                ScrollIndicator.vertical: ScrollIndicator {}
                property var _page: root

                delegate: RuleCard {
                    width: ListView.view.width
                    ruleData: modelData
                    highlighted: RulePresenter.selectedRule.name === modelData.name

                    onClicked: function(rule) {
                        RulePresenter.selectRule(rule.name);
                    }
                    onEditRequested: function(rule) {
                        editDialog.editRule = rule;
                        editDialog.open();
                    }
                    // qmllint disable missing-property
                    onDeleteRequested: function(rule) {
                        RulePresenter.deleteRule(rule.name);
                        ListView.view._page._clearSelection();
                    }
                    onDuplicateRequested: function(rule) {
                        RulePresenter.duplicateRule(rule.name);
                    }
                    // qmllint enable missing-property
                }
            }
    }

    // ==== 编辑对话框 ====
    RuleEditDialog {
        id: editDialog
        editRule: ({})
        onAccepted: RulePresenter.reload()
    }

    // ==== 测试结果对话框 ====
    RuleTestResultDialog {
        id: testResultDialog
    }

    // ==== 测试结果监听 ====
    Connections {
        target: RulePresenter
        function onTestResultReady(result) {
            testStatusText.text = "";
            testResultDialog.resultData = result;
            testResultDialog.open();
        }
        function onTestStatusChanged(status) {
            testStatusText.text = status;
        }
    }

    // ==== 文件对话框 ====
    FileDialog {
        id: fileImportDialog
        title: "导入规则"
        fileMode: FileDialog.OpenFile
        nameFilters: ["JSON 文件 (*.json)"]
        onAccepted: {
            RulePresenter.importFromFile(selectedFile);
        }
    }

    FileDialog {
        id: fileExportSelectedDialog
        title: "导出选中规则"
        fileMode: FileDialog.SaveFile
        nameFilters: ["JSON 文件 (*.json)"]
        onAccepted: {
            RulePresenter.exportRules(_selectedNames(), selectedFile);
            root._clearSelection();
        }
    }
    }
}