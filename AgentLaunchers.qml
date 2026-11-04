pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Item {
    id: root

    // Injected by the Omarchy bar runtime.
    property var bar
    property string moduleName
    property var settings

    // All launchers intentionally use ~/Work as their workspace.
    readonly property string pluginDir: Quickshell.env("HOME") + "/.config/omarchy/plugins/mst.agent-launchers"

    property bool codexResumable: false
    property bool agyResumable: false
    property bool claudeResumable: false
    property string codexTooltip: "Codex\nStatus wird geladen …"
    property string agyTooltip: "Agy\nStatus wird geladen …"
    property string claudeTooltip: "Claude\nStatus wird geladen …"

    implicitWidth: button.width
    implicitHeight: button.height

    property bool menuOpen: false
    // Recent and running sessions of all agents (bin/agent-launcher-status
    // --sessions), read only when the menu opens.
    property var sessionList: []
    property bool sessionsLoading: false
    property string expandedAgent: ""

    readonly property bool anyResumable: codexResumable || agyResumable || claudeResumable
    readonly property string combinedTooltip: claudeTooltip + "\n\n" + codexTooltip + "\n\n" + agyTooltip
        + "\n\nKlick: Agent-Menü · Mitte: Status neu lesen"
    readonly property color foreground: bar ? bar.foreground : Commons.Color.foreground
    readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family

    // Called by PopupCard on outside click.
    function close() {
        menuOpen = false
        expandedAgent = ""
    }

    function sessionsFor(agent) {
        var out = []
        for (var i = 0; i < sessionList.length; i++)
            if (sessionList[i].agent === agent)
                out.push(sessionList[i])
        return out
    }

    function launchAgent(agent, resume) {
        menuOpen = false
        expandedAgent = ""
        if (!bar)
            return

        var command
        if (agent === "codex")
            command = resume ? "codex resume --last" : "codex"
        else if (agent === "claude")
            command = resume ? "claude --continue" : "claude"
        else
            command = resume ? "agy -c" : "agy"

        // No automatic switching, no default-agent mutation and no
        // --dangerously-skip-permissions. The user chooses the agent explicitly.
        bar.run("cd \"$HOME/Work\" && omarchy-launch-tui --app-id=org.omarchy.agent " + command)
    }

    function openSession(item) {
        menuOpen = false
        expandedAgent = ""
        if (!bar || !item)
            return
        // Running session: bring its window to the front instead of starting
        // a second client on the same transcript.
        if (item.active && item.focusPid > 0)
            bar.run("hyprctl dispatch focuswindow pid:" + Number(item.focusPid))
        else if (item.command)
            bar.run(String(item.command))
    }

    function refreshSessions() {
        if (!sessionsProcess.running) {
            sessionsLoading = true
            sessionsProcess.running = true
        }
    }

    function resumableFor(agent) {
        if (agent === "codex")
            return codexResumable
        if (agent === "claude")
            return claudeResumable
        return agyResumable
    }

    function refreshStatus() {
        if (!statusProcess.running)
            statusProcess.running = true
    }

    function applyStatus(text) {
        try {
            var data = JSON.parse(String(text || "{}"))
            if (data.codex) {
                codexResumable = data.codex.resumable === true
                codexTooltip = String(data.codex.tooltip || "Codex")
            }
            if (data.agy) {
                agyResumable = data.agy.resumable === true
                agyTooltip = String(data.agy.tooltip || "Agy")
            }
            if (data.claude) {
                claudeResumable = data.claude.resumable === true
                claudeTooltip = String(data.claude.tooltip || "Claude")
            }
        } catch (e) {
            codexTooltip = "Codex\nStatus konnte nicht gelesen werden"
            agyTooltip = "Agy\nStatus konnte nicht gelesen werden"
            claudeTooltip = "Claude\nStatus konnte nicht gelesen werden"
        }
    }

    Process {
        id: statusProcess
        command: [root.pluginDir + "/bin/agent-launcher-status"]
        stdout: StdioCollector {
            id: statusStdout
            waitForEnd: true
        }
        onExited: function(exitCode) {
            if (exitCode === 0)
                root.applyStatus(statusStdout.text)
        }
    }

    Process {
        id: sessionsProcess
        command: [root.pluginDir + "/bin/agent-launcher-status", "--sessions"]
        stdout: StdioCollector {
            id: sessionsStdout
            waitForEnd: true
        }
        onExited: function(exitCode) {
            root.sessionsLoading = false
            if (exitCode !== 0)
                return
            try {
                root.sessionList = JSON.parse(String(sessionsStdout.text || "{}")).sessions || []
            } catch (e) {
                root.sessionList = []
            }
        }
    }

    Timer {
        interval: 60000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: root.refreshStatus()
    }

    Item {
        id: button
        width: Style.bar.iconSlot
        height: root.bar ? root.bar.barSize : 26

        Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: 4
            color: root.bar ? root.bar.foreground : "white"
            opacity: mouse.containsMouse ? 0.14 : 0.0
        }

        Image {
            id: agentIcon
            anchors.centerIn: parent
            width: Math.max(14, button.height - 12)
            height: width
            source: Qt.resolvedUrl("assets/agents.svg")
            sourceSize.width: width * 2
            sourceSize.height: height * 2
            fillMode: Image.PreserveAspectFit
            smooth: true
            visible: false
            layer.enabled: true
        }

        MultiEffect {
            anchors.fill: agentIcon
            source: agentIcon
            colorization: 1.0
            colorizationColor: root.bar ? root.bar.foreground : "white"
        }

        Rectangle {
            visible: root.anyResumable
            width: 5
            height: 5
            radius: 2.5
            anchors.right: agentIcon.right
            anchors.top: agentIcon.top
            color: root.bar ? root.bar.foreground : "white"
            border.width: 1
            border.color: root.bar ? root.bar.background : "black"
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton

            onEntered: {
                root.refreshStatus()
                if (root.bar && !root.menuOpen)
                    root.bar.showTooltip(button, root.combinedTooltip)
            }

            onExited: {
                if (root.bar)
                    root.bar.hideTooltip(button)
            }

            onClicked: function(mouseEvent) {
                if (mouseEvent.button === Qt.MiddleButton) {
                    root.refreshStatus()
                    return
                }
                if (root.bar)
                    root.bar.hideTooltip(button)
                if (!root.menuOpen) {
                    root.refreshStatus()
                    root.refreshSessions()
                }
                root.menuOpen = !root.menuOpen
                if (!root.menuOpen)
                    root.expandedAgent = ""
            }
        }
    }

    PopupCard {
        id: menuPopup
        anchorItem: button
        owner: root
        bar: root.bar
        open: root.menuOpen
        padding: Style.space(6)
        borderColor: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.45)
        contentWidth: menuPopup.fittedContentWidth(Style.space(root.expandedAgent ? 280 : 190))
        contentHeight: menuPopup.fittedContentHeight(menuColumn.implicitHeight)

        Column {
            id: menuColumn
            anchors.fill: parent
            spacing: 0

            Repeater {
                model: [
                    { "label": "Claude", "agent": "claude", "resume": false },
                    { "label": "Claude fortsetzen", "agent": "claude", "resume": true },
                    { "separator": true },
                    { "label": "Codex", "agent": "codex", "resume": false },
                    { "label": "Codex fortsetzen", "agent": "codex", "resume": true },
                    { "separator": true },
                    { "label": "Agy", "agent": "agy", "resume": false },
                    { "label": "Agy fortsetzen", "agent": "agy", "resume": true }
                ]

                delegate: Column {
                    id: menuRow
                    required property var modelData
                    readonly property bool separator: modelData.separator === true
                    readonly property bool isResume: !separator && modelData.resume === true
                    readonly property bool expanded: isResume && root.expandedAgent === modelData.agent
                    readonly property var agentSessions: isResume ? root.sessionsFor(modelData.agent) : []
                    // Resume without a detected ~/Work session stays usable but dimmed.
                    readonly property bool resumeAvailable: isResume && (root.resumableFor(modelData.agent) || agentSessions.length > 0)

                    width: menuColumn.width
                    spacing: 0

                    Item {
                        width: menuRow.width
                        height: menuRow.separator ? Style.space(9) : Style.space(28)

                        Rectangle {
                            visible: menuRow.separator
                            anchors.left: parent.left
                            anchors.leftMargin: Style.space(8)
                            anchors.right: parent.right
                            anchors.rightMargin: Style.space(8)
                            anchors.verticalCenter: parent.verticalCenter
                            height: 1
                            color: Commons.Color.popups.border
                            opacity: 0.45
                        }

                        Rectangle {
                            visible: !menuRow.separator
                            anchors.fill: parent
                            radius: Math.max(2, Style.cornerRadius)
                            color: rowMouse.containsMouse ? Style.hoverFillFor(root.foreground, root.foreground) : "transparent"
                        }

                        Text {
                            visible: !menuRow.separator
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.left: parent.left
                            anchors.leftMargin: Style.space(10)
                            text: String(menuRow.modelData.label || "")
                            color: root.foreground
                            opacity: menuRow.isResume && !menuRow.resumeAvailable ? 0.5 : 1.0
                            font.family: root.fontFamily
                            font.pixelSize: Style.font.bodySmall
                        }

                        Text {
                            visible: menuRow.isResume
                            anchors.verticalCenter: parent.verticalCenter
                            anchors.right: parent.right
                            anchors.rightMargin: Style.space(10)
                            text: (menuRow.resumeAvailable ? "• " : "") + (menuRow.expanded ? "▾" : "▸")
                            color: root.foreground
                            font.family: root.fontFamily
                            font.pixelSize: Style.font.bodySmall
                        }

                        MouseArea {
                            id: rowMouse
                            visible: !menuRow.separator
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (menuRow.isResume)
                                    root.expandedAgent = menuRow.expanded ? "" : menuRow.modelData.agent
                                else
                                    root.launchAgent(menuRow.modelData.agent, false)
                            }
                        }
                    }

                    // Unterpunkte: zuletzt benutzte Sitzung in ~/Work, dann die Liste.
                    Repeater {
                        model: menuRow.expanded
                            ? [{ "kind": "last" }].concat(menuRow.agentSessions.length > 0 ? menuRow.agentSessions
                                : [{ "kind": "empty" }])
                            : []

                        delegate: Item {
                            id: subRow
                            required property var modelData
                            readonly property bool isLast: modelData.kind === "last"
                            readonly property bool isEmpty: modelData.kind === "empty"

                            width: menuRow.width
                            height: subRow.isLast || subRow.isEmpty ? Style.space(26) : Style.space(38)

                            Rectangle {
                                visible: !subRow.isEmpty
                                anchors.fill: parent
                                radius: Math.max(2, Style.cornerRadius)
                                color: subMouse.containsMouse ? Style.hoverFillFor(root.foreground, root.foreground) : "transparent"
                            }

                            Text {
                                id: subTitle
                                anchors.left: parent.left
                                anchors.leftMargin: Style.space(24)
                                anchors.right: parent.right
                                anchors.rightMargin: Style.space(10)
                                anchors.top: parent.top
                                anchors.topMargin: subRow.isLast || subRow.isEmpty ? Style.space(6) : Style.space(3)
                                elide: Text.ElideRight
                                text: subRow.isLast ? "Letzte Sitzung in ~/Work"
                                    : subRow.isEmpty ? "keine weiteren Sitzungen (14 Tage)"
                                    : (subRow.modelData.active ? "● " : "") + String(subRow.modelData.title || "")
                                color: root.foreground
                                opacity: subRow.isEmpty ? 0.5 : 1.0
                                font.family: root.fontFamily
                                font.pixelSize: Style.font.bodySmall
                            }

                            Text {
                                visible: !subRow.isLast && !subRow.isEmpty
                                anchors.left: subTitle.left
                                anchors.right: subTitle.right
                                anchors.top: subTitle.bottom
                                elide: Text.ElideRight
                                text: String(subRow.modelData.detail || "")
                                color: root.foreground
                                opacity: 0.55
                                font.family: root.fontFamily
                                font.pixelSize: Math.max(9, Style.font.bodySmall - 2)
                            }

                            MouseArea {
                                id: subMouse
                                visible: !subRow.isEmpty
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    if (subRow.isLast)
                                        root.launchAgent(menuRow.modelData.agent, true)
                                    else
                                        root.openSession(subRow.modelData)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
