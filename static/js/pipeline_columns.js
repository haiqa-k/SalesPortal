document.addEventListener("DOMContentLoaded", function () {

    const selectors =
        document.querySelectorAll(".column-selector");

    selectors.forEach(selector => {

        const toggles =
            selector.querySelectorAll(".column-toggle");

        const showAllButton =
            selector.querySelector(".show-all-columns");

        const resetButton =
            selector.querySelector(".reset-columns");


        // Save the original/default state
        const defaults = {};

        toggles.forEach(toggle => {

            defaults[toggle.dataset.column] =
                toggle.checked;

        });


        function setColumnVisibility(
            columnName,
            visible
        ) {

            const cells =
                document.querySelectorAll(
                    `[data-col="${columnName}"]`
                );

            cells.forEach(cell => {

                cell.style.display =
                    visible ? "" : "none";

            });

        }


        // Checkbox changed
        toggles.forEach(toggle => {

            toggle.addEventListener(
                "change",
                function () {

                    setColumnVisibility(
                        this.dataset.column,
                        this.checked
                    );

                }
            );

        });


        // Apply initial visibility
        toggles.forEach(toggle => {

            setColumnVisibility(
                toggle.dataset.column,
                toggle.checked
            );

        });


        // Show all
        if (showAllButton) {

            showAllButton.addEventListener(
                "click",
                function () {

                    toggles.forEach(toggle => {

                        toggle.checked = true;

                        setColumnVisibility(
                            toggle.dataset.column,
                            true
                        );

                    });

                }
            );

        }


        // Reset
        if (resetButton) {

            resetButton.addEventListener(
                "click",
                function () {

                    toggles.forEach(toggle => {

                        const column =
                            toggle.dataset.column;

                        toggle.checked =
                            defaults[column];

                        setColumnVisibility(
                            column,
                            defaults[column]
                        );

                    });

                }
            );

        }

    });

});