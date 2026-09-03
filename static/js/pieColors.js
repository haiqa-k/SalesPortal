const pieColors = {
    "Customer Visit (20%)": "#2196F3",
    "Ask for Proposal (40%)": "#FFC107",
    "Negotiations (60%)": "#F44336",
    "Documentation/Acceptance/Processing (80%)": "#FF9800",
    "System Entry/Revenue Locked (100%)": "#4CAF50",
    "Lost to Competitor": "#4f4d4d",
    "Retired - No Decision": "#91146b"
};


function getPieColors(statuses) {
    return statuses.map(
        status =>
            pieColors[status] || "#616161"
    );
}

/*
'#2196F3',  // Customer Visit
                            '#FFC107',  // Proposal
                            '#9C27B0',  // Negotiations
                            '#F44336',  // Processing
                            '#4CAF50',  // Revenue Locked
                            '#F44336',  // Lost
                            '#757575'   // Retired



                                "Customer Visit (20%)": "#2196F3",
                                "Ask for Proposal (40%)": "#FFC107",
                                "Negotiations (60%)": "#9C27B0",
                                "Documentation/Acceptance/Processing (80%)": "#FF9800",
                                "System Entry/Revenue Locked (100%)": "#4CAF50",
                                "Lost to Competitor": "#F44336",
                                "Retired - No Decision": "#757575"

                            */