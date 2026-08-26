import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import GenshinUI

// qmllint disable unqualified

Dialog {
    id: root
    property var editRule: ({})
    modal: true
    width: 460
    height: 540
    anchors.centerIn: Overlay.overlay
    padding: 0
    title: "新建规则"

    // —— 表单本地状态 ——
    property string _formName: ""
    property string _formPart: "*"
    property string _formPartExclude: ""
    property string _formMainStat: "*"
    property bool _formSetEnabled: true
    property string _formSetName: ""
    property string _formSetSearch: ""
    property var _formSelectedSets: []
    property string _formSubStats: ""
    property var _formSelectedSubStats: []
    property bool _formSubStatsPopupOpen: false
    property int _formSubCount: 0
    property string _formAction: "keep"
    property int _formPriority: 0
    property bool _formEnabled: true
    property bool _formIncludeUnactivated: true
    property bool _formIncludeMainStat: false

    // —— 动态词条过滤 ——
    property var _mainStatOptions: RulePresenter.getMainStatOptions(root._formPart)
    property var _filteredSubStats: RulePresenter.getFilteredSubStats(root._formMainStat)

    onOpened: {
        const defaults = RulePresenter.buildFormDefaults(editRule || {});
        root.title = defaults.title;
        _formName = defaults.name;
        _formPart = defaults.part;
        _formPartExclude = defaults.part_exclude;
        _formMainStat = defaults.main_stat;
        _formSetEnabled = defaults.set_enabled;
        _formSelectedSets = defaults.selected_sets;
        _formSetSearch = defaults.set_search;
        _formSubStats = defaults.selected_sub_stats.map(function(s) { return s.name; }).join(", ");
        _formSelectedSubStats = defaults.selected_sub_stats;
        _formSubCount = defaults.sub_count;
        _formAction = defaults.action;
        _formPriority = defaults.priority;
        _formEnabled = defaults.enabled;
        _formIncludeUnactivated = defaults.include_unactivated;
        _formIncludeMainStat = defaults.include_main_stat;
    }

    // —— 辅助函数（供 Repeater delegate 调用） ——
    function removeSelectedSet(setName) {
        var arr = _formSelectedSets.slice();
        var idx = arr.indexOf(setName);
        if (idx >= 0) {
            arr.splice(idx, 1);
            _formSelectedSets = arr;
            _formSetName = arr.join(",");
        }
    }

    function removeSelectedSubStat(index) {
        var arr = _formSelectedSubStats.slice();
        arr.splice(index, 1);
        _formSelectedSubStats = arr;
        _formSubStats = arr.map(function(s) { return s.name; }).join(", ");
    }

    function updateSubStatCondition(index, op, value) {
        var arr = _formSelectedSubStats.slice();
        arr[index] = { name: arr[index].name, op: op, value: value };
        _formSelectedSubStats = arr;
        _formSubStats = arr.map(function(s) { return s.name; }).join(", ");
    }

    // —— 背景 ——
    background: Rectangle {
        radius: 10
        color: Theme.bgPrimary
        border.color: Theme.border
    }

    // —— 自定义 header ——
    header: Rectangle {
        implicitHeight: 44
        color: "transparent"
        Text {
            anchors.centerIn: parent
            text: root.title
            font.family: Theme.fontFamily
            font.pixelSize: 16
            font.bold: true
            color: Theme.textPrimary
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: Theme.border
        }
    }

    // —— 自定义 footer ——
    footer: Rectangle {
        implicitHeight: 48
        color: "transparent"
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            color: Theme.border
        }
        RowLayout {
            anchors.right: parent.right
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8
            GButton {
                text: "取消"
                colorType: "default"
                onClicked: root.reject()
            }
            GButton {
                text: "保存"
                colorType: "primary"
                onClicked: {
                    const data = RulePresenter.buildSaveData({
                        name: root._formName,
                        _original_name: (root.editRule && root.editRule.name) ? root.editRule.name : "",
                        part: root._formPart,
                        part_exclude: root._formPartExclude,
                        main_stat: root._formMainStat,
                        set_enabled: root._formSetEnabled,
                        selected_sets: root._formSelectedSets,
                        sub_stats: root._formSelectedSubStats,
                        sub_count: root._formSubCount,
                        action: root._formAction,
                        priority: root._formPriority,
                        enabled: root._formEnabled,
                        include_unactivated: root._formIncludeUnactivated,
                        include_main_stat: root._formIncludeMainStat,
                    });
                    const result = RulePresenter.saveRule(data);
                    if (result && result.ok) {
                        root.accept();
                    } else if (result) {
                        errorBox.msgType = "warning";
                        errorBox.msgText = result.message || "保存失败";
                        errorBox.open();
                    }
                }
            }
        }
    }

    // —— 内容 ——
    contentItem: ScrollView {
        contentWidth: width
        clip: true

        ColumnLayout {
            width: parent.width - 40
            x: 20
            y: 16
            spacing: 14

            // ========== 基础信息 ==========
            SectionLabel {
                text: "▎基础信息"
            }

            FormRow {
                label: "名称"
                Layout.fillWidth: true
                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    radius: Theme.radius
                    color: Theme.bgTrack
                    border.color: nameInput.activeFocus ? Theme.accent : Theme.border
                    HoverHandler {
                        cursorShape: Qt.IBeamCursor
                    }
                    TextInput {
                        id: nameInput
                        anchors.fill: parent
                        anchors.margins: 8
                        font.family: Theme.fontFamily
                        font.pixelSize: 14
                        color: Theme.textPrimary
                        verticalAlignment: Text.AlignVCenter
                        text: root._formName
                        onTextChanged: root._formName = text
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                text: "为规则起一个易于识别的名称"
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            // ========== 筛选条件 ==========
            SectionLabel {
                text: "▎筛选条件"
            }

            // 部位 + 排除
            FormRow {
                label: "部位"
                Layout.fillWidth: true
                GComboBox {
                    id: partCombo
                    implicitWidth: 120
                    model: ["不限", "生之花", "死之羽", "时之沙", "空之杯", "理之冠"]
                    currentIndex: {
                        const display = root._formPart === "*" ? "不限" : root._formPart;
                        const idx = partCombo.find(display);
                        return idx >= 0 ? idx : 0;
                    }
                    onActivated: function (idx) {
                        const v = partCombo.textAt(idx);
                        root._formPart = v === "不限" ? "*" : v;
                        if (!RulePresenter.validateMainStatForPart(root._formPart, root._formMainStat)) {
                            root._formMainStat = "*";
                        }
                    }
                }
                Text {
                    text: "排除"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                }
                GComboBox {
                    id: partExcludeCombo
                    implicitWidth: 120
                    model: ["不排除", "生之花", "死之羽", "时之沙", "空之杯", "理之冠"]
                    currentIndex: {
                        const display = root._formPartExclude === "" ? "不排除" : root._formPartExclude;
                        const idx = partExcludeCombo.find(display);
                        return idx >= 0 ? idx : 0;
                    }
                    onActivated: function (idx) {
                        const v = partExcludeCombo.textAt(idx);
                        root._formPartExclude = v === "不排除" ? "" : v;
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                text: "'部位'匹配白名单，'排除'为黑名单，两者互不冲突"
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            // 主词条
            FormRow {
                label: "主词条"
                Layout.fillWidth: true
                GComboBox {
                    id: mainStatCombo
                    implicitWidth: 200
                    model: root._mainStatOptions
                    currentIndex: {
                        const display = root._formMainStat === "*" ? "不限" : root._formMainStat;
                        const idx = root._mainStatOptions.indexOf(display);
                        return idx >= 0 ? idx : 0;
                    }
                    onActivated: function (idx) {
                        const v = root._mainStatOptions[idx];
                        root._formMainStat = v === "不限" ? "*" : v;
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                text: "主词条会根据部位自动过滤可选范围"
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            // 套装
            FormRow {
                label: "套装"
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    // 不限 / 指定 切换
                    RowLayout {
                        spacing: 0
                        Rectangle {
                            implicitWidth: 80
                            implicitHeight: 28
                            radius: Theme.radius
                            color: Theme.bgTrack
                            RowLayout {
                                anchors.fill: parent
                                spacing: 0
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    radius: Theme.radius
                                    color: root._formSetEnabled ? Theme.accent : "transparent"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "不限"
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: root._formSetEnabled ? Theme.bgPrimary : Theme.textSecondary
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            root._formSetEnabled = true;
                                        }
                                    }
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true
                                    radius: Theme.radius
                                    color: !root._formSetEnabled ? Theme.accent : "transparent"
                                    Text {
                                        anchors.centerIn: parent
                                        text: "指定"
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: !root._formSetEnabled ? Theme.bgPrimary : Theme.textSecondary
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            root._formSetEnabled = false;
                                            root._formSetName = root._formSelectedSets.join(",");
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // 指定套装时展开
                    ColumnLayout {
                        visible: !root._formSetEnabled
                        spacing: 4

                        // 选择按钮
                        RowLayout {
                            spacing: 4
                            Rectangle {
                                id: setBtn
                                height: 28
                                width: setBtnText.implicitWidth + 28
                                radius: Theme.radius
                                color: Theme.bgTrack
                                border.color: Theme.border
                                RowLayout {
                                    anchors.centerIn: parent
                                    spacing: 4
                                    Text {
                                        id: setBtnText
                                        text: root._formSelectedSets.length > 0 ? "已选 " + root._formSelectedSets.length + " 个" : "选择套装"
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.textSecondary
                                    }
                                    Text {
                                        text: "▾"
                                        font.pixelSize: 10
                                        color: Theme.textMuted
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: setPopup.open()
                                }
                            }
                            Item {
                                Layout.fillWidth: true
                            }
                        }

                        // 已选标签
                        Flow {
                            Layout.fillWidth: true
                            spacing: 4
                            layoutDirection: Qt.LeftToRight
                            visible: root._formSelectedSets.length > 0
                            Repeater {
                                model: root._formSelectedSets
                                delegate: Rectangle {
                                    required property string modelData
                                    height: 24
                                    width: Math.min(chipRow.implicitWidth + 28, 180)
                                    radius: 12
                                    color: Theme.accentOverlay6
                                    RowLayout {
                                        id: chipRow
                                        anchors.left: parent.left
                                        anchors.leftMargin: 8
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 4
                                        Image {
                                            width: 16
                                            height: 16
                                            source: {
                                                var sets = RulePresenter.artifactSetNames || [];
                                                for (let i = 0; i < sets.length; i++) {
                                                    if (sets[i].name === modelData)
                                                        return sets[i].icon;
                                                }
                                                return "";
                                            }
                                            sourceSize: Qt.size(16, 16)
                                            asynchronous: true
                                            fillMode: Image.PreserveAspectFit
                                            mipmap: true
                                        }
                                        Text {
                                            text: modelData
                                            font.family: Theme.fontFamily
                                            font.pixelSize: 11
                                            color: Theme.accent
                                            elide: Text.ElideRight
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: removeSelectedSet(modelData)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                text: "选择'不限'匹配所有套装，选择'指定'可多选特定套装"
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            // 副词条
            FormRow {
                label: "副词条"
                Layout.fillWidth: true
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    GButton {
                        id: subStatsBtn
                        text: root._formSelectedSubStats.length > 0 ? "已选 " + root._formSelectedSubStats.length + " 个" : "不限"
                        colorType: "default"
                        implicitHeight: 32
                        onClicked: {
                            subStatsPopup.visible = !subStatsPopup.visible;
                        }
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 4
                        Repeater {
                            model: root._formSelectedSubStats
                            delegate: Rectangle {
                                required property var modelData
                                required property int index
                                width: tagRow.implicitWidth + 16
                                height: 24
                                radius: 12
                                color: Theme.accentOverlay6
                                RowLayout {
                                    id: tagRow
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 4
                                    Text {
                                        text: {
                                            var s = modelData.name;
                                            if (modelData.op && modelData.op !== "") {
                                                s += " " + modelData.op + " " + modelData.value;
                                            }
                                            return s;
                                        }
                                        font.family: Theme.fontFamily
                                        font.pixelSize: 12
                                        color: Theme.accent
                                    }
                                    Text {
                                        text: "✕"
                                        font.pixelSize: 10
                                        color: Theme.textMuted
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: removeSelectedSubStat(index)
                                        }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        subStatEditPopup._editIndex = index;
                                        subStatEditPopup._editOp = modelData.op || "";
                                        subStatEditPopup._editValue = modelData.value || 0;
                                        const pos = parent.mapToItem(root.contentItem, parent.x, parent.y);
                                        subStatEditPopup.x = pos.x;
                                        subStatEditPopup.y = pos.y + parent.height + 2;
                                        subStatEditPopup.open();
                                    }
                                }
                            }
                        }
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                text: "勾选副词条后，点击标签可设置值条件（大于/小于等），副词条与主词条冲突的选项会自动排除"
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            // 匹配数 + 行为
            FormRow {
                label: "满足词条数"
                Layout.fillWidth: true
                GSpinBox {
                    id: subCountSpin
                    from: 0
                    to: 4
                    implicitHeight: 32
                    value: root._formSubCount
                    onValueChanged: root._formSubCount = value
                }
                Item {
                    Layout.preferredWidth: 16
                }
                Text {
                    text: "命中后"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                }
                GComboBox {
                    id: actionCombo
                    implicitWidth: 80
                    model: ["保留", "分解"]
                    currentIndex: root._formAction === "discard" ? 1 : 0
                    onActivated: function (idx) {
                        root._formAction = idx === 1 ? "discard" : "keep";
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                text: "需要至少命中 N 个副词条条件，才视为匹配成功"
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                spacing: 8
                GCheckBox {
                    id: includeUnactivatedCb
                    checked: root._formIncludeUnactivated
                    onCheckedChanged: root._formIncludeUnactivated = checked
                }
                Text {
                    text: "副词条匹配时考虑待激活词条"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                spacing: 8
                GCheckBox {
                    id: includeMainStatCb
                    checked: root._formIncludeMainStat
                    onCheckedChanged: root._formIncludeMainStat = checked
                }
                Text {
                    text: "主词条也计入副词条匹配数"
                    font.family: Theme.fontFamily
                    font.pixelSize: 13
                    color: Theme.textSecondary
                }
            }

            // ========== 其他 ==========
            SectionLabel {
                text: "▎其他"
            }

            FormRow {
                label: "优先级"
                Layout.fillWidth: true
                GSpinBox {
                    id: prioritySpin
                    from: 0
                    to: 100
                    implicitHeight: 32
                    value: root._formPriority
                    onValueChanged: root._formPriority = value
                }
                Item {
                    Layout.preferredWidth: 16
                }
                GCheckBox {
                    id: enabledCheck
                    text: "启用"
                    checked: root._formEnabled
                onCheckedChanged: root._formEnabled = checked
            }
        }
            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 68
                text: "数值越大优先级越高，多条规则命中时按最高优先级执行；关闭'启用'后规则暂不生效"
                font.family: Theme.fontFamily
                font.pixelSize: 11
                color: Theme.textMuted
                wrapMode: Text.WordWrap
            }

            Item {
                height: 16
            }
        }
    }

    // —— 副词条选择弹窗 ——
    Popup {
        id: subStatsPopup
        width: 200
        height: Math.min(subStatsList.contentHeight, 260)
        padding: 4
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onOpened: {
            const pos = subStatsBtn.mapToItem(root.contentItem, 0, 0);
            x = pos.x;
            y = pos.y + subStatsBtn.height + 2;
        }
        contentItem: ListView {
            id: subStatsList
            clip: true
            model: root._filteredSubStats
            delegate: ItemDelegate {
                width: subStatsList.width
                height: 32
                required property string modelData
                checkable: true
                checked: {
                    const arr = root._formSelectedSubStats;
                    for (let i = 0; i < arr.length; i++) {
                        if (arr[i].name === modelData)
                            return true;
                    }
                    return false;
                }
                onToggled: {
                    const arr = root._formSelectedSubStats.slice();
                    if (checked) {
                        arr.push({ name: modelData, op: "", value: 0 });
                    } else {
                        for (let i = 0; i < arr.length; i++) {
                            if (arr[i].name === modelData) {
                                arr.splice(i, 1);
                                break;
                            }
                        }
                    }
                    root._formSelectedSubStats = arr;
                    root._formSubStats = arr.map(function(s) { return s.name; }).join(", ");
                }
                contentItem: Text {
                    text: modelData
                    font.family: Theme.fontFamily
                    font.pixelSize: 14
                    color: Theme.textPrimary
                    verticalAlignment: Text.AlignVCenter
                    elide: Text.ElideRight
                }
                background: Rectangle {
                    color: checked ? Theme.accentOverlay6 : "transparent"
                    radius: 4
                }
            }
        }
        background: Rectangle {
            color: Theme.bgSecondary
            radius: 8
            border.color: Theme.border
        }
    }

    // —— 套装选择弹窗 ——
    Popup {
        id: setPopup
        width: 300
        height: 280
        padding: 8
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        onOpened: {
            var pos = setBtn.mapToItem(root.contentItem, 0, 0);
            x = pos.x;
            y = pos.y + setBtn.height + 2;
        }
        background: Rectangle {
            radius: 8
            color: Theme.bgPrimary
            border.color: Theme.border
        }
        ColumnLayout {
            anchors.fill: parent
            spacing: 6
            Rectangle {
                Layout.fillWidth: true
                height: 28
                radius: Theme.radius
                color: Theme.bgTrack
                border.color: popupSearchInput.activeFocus ? Theme.accent : Theme.border
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 4
                    Text {
                        text: "🔍"
                        font.pixelSize: 12
                    }
                    TextInput {
                        id: popupSearchInput
                        Layout.fillWidth: true
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.textPrimary
                        verticalAlignment: Text.AlignVCenter
                        text: root._formSetSearch
                        onTextChanged: root._formSetSearch = text
                    }
                }
                HoverHandler {
                    cursorShape: Qt.IBeamCursor
                }
            }
            ListView {
                id: setListView
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: {
                    const all = RulePresenter.artifactSetNames || [];
                    if (all.length === 0)
                        return [];
                    if (root._formSetSearch === "")
                        return all;
                    const kw = root._formSetSearch.toLowerCase();
                    return all.filter(function (item) {
                        return item.name.toLowerCase().includes(kw);
                    });
                }
                delegate: ItemDelegate {
                    width: ListView.view.width
                    height: 32
                    required property var modelData
                    contentItem: RowLayout {
                        spacing: 6
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignLeft
                        Rectangle {
                            width: 14
                            height: 14
                            radius: 3
                            color: root._formSelectedSets.indexOf(modelData.name) >= 0 ? Theme.accent : "transparent"
                            border.color: Theme.border
                            Text {
                                anchors.centerIn: parent
                                visible: root._formSelectedSets.indexOf(modelData.name) >= 0
                                text: "✓"
                                font.pixelSize: 10
                                color: Theme.bgPrimary
                            }
                        }
                        Image {
                            width: 24
                            height: 24
                            source: modelData.icon
                            sourceSize: Qt.size(24, 24)
                            asynchronous: true
                            fillMode: Image.PreserveAspectFit
                            mipmap: true
                        }
                        Text {
                            text: modelData.name
                            font.family: Theme.fontFamily
                            font.pixelSize: 13
                            color: Theme.textPrimary
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }
                    onClicked: {
                        var arr = root._formSelectedSets.slice();
                        var idx = arr.indexOf(modelData.name);
                        if (idx >= 0) {
                            arr.splice(idx, 1);
                        } else {
                            arr.push(modelData.name);
                        }
                        root._formSelectedSets = arr;
                        root._formSetName = arr.join(",");
                    }
                }
                ScrollBar.vertical: ScrollBar {}
            }

            Text {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: {
                    const all = RulePresenter.artifactSetNames || [];
                    return all.length === 0;
                }
                text: "暂无套装数据，请先同步圣遗物数据"
                font.family: Theme.fontFamily
                font.pixelSize: 13
                color: Theme.textSecondary
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }

    // —— 副词条条件编辑弹窗 ——
    Popup {
        id: subStatEditPopup
        width: 220
        height: 120
        padding: 8
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        property int _editIndex: -1
        property string _editOp: ""
        property double _editValue: 0

        background: Rectangle {
            color: Theme.bgSecondary
            radius: 8
            border.color: Theme.border
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 8
            Text {
                text: "比较条件"
                font.family: Theme.fontFamily
                font.pixelSize: 12
                font.bold: true
                color: Theme.textPrimary
            }
            RowLayout {
                spacing: 6
                GComboBox {
                    id: opCombo
                    implicitWidth: 90
                    model: ["任意值", ">", "<", ">=", "<=", "="]
                    currentIndex: {
                        if (subStatEditPopup._editOp === "") return 0;
                        const idx = opCombo.find(subStatEditPopup._editOp);
                        return idx >= 0 ? idx : 0;
                    }
                    onActivated: function(idx) {
                        subStatEditPopup._editOp = idx === 0 ? "" : opCombo.textAt(idx);
                    }
                }
                Rectangle {
                    visible: subStatEditPopup._editOp !== ""
                    width: 80
                    height: 28
                    radius: 4
                    color: Theme.bgTrack
                    border.color: valueInput.activeFocus ? Theme.accent : Theme.border
                    HoverHandler {
                        cursorShape: Qt.IBeamCursor
                    }
                    TextInput {
                        id: valueInput
                        anchors.fill: parent
                        anchors.margins: 6
                        font.family: Theme.fontFamily
                        font.pixelSize: 13
                        color: Theme.textPrimary
                        verticalAlignment: Text.AlignVCenter
                        validator: DoubleValidator { bottom: 0; decimals: 1; notation: DoubleValidator.StandardNotation }
                        text: subStatEditPopup._editValue !== 0 ? subStatEditPopup._editValue : ""
                        onTextChanged: {
                            const v = parseFloat(text);
                            subStatEditPopup._editValue = isNaN(v) ? 0 : v;
                        }
                    }
                }
            }
            GButton {
                text: "确定"
                colorType: "primary"
                implicitHeight: 28
                Layout.alignment: Qt.AlignRight
                onClicked: {
                    if (subStatEditPopup._editIndex >= 0) {
                        updateSubStatCondition(subStatEditPopup._editIndex, subStatEditPopup._editOp, subStatEditPopup._editValue);
                    }
                    subStatEditPopup.close();
                }
            }
        }
    }

    // ========== 内联组件 ==========
    component SectionLabel: Text {
        font.family: Theme.fontFamily
        font.pixelSize: 12
        font.bold: true
        color: Theme.accent
    }

    component FormRow: RowLayout {
        property string label: ""
        spacing: 8
        Text {
            text: parent.label
            font.family: Theme.fontFamily
            font.pixelSize: 13
            color: Theme.textSecondary
            Layout.preferredWidth: 60
            Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
        }
    }
    GMessageBox {
        id: errorBox
    }
}