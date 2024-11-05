document.addEventListener("DOMContentLoaded", function () {
    const uploadForm = document.getElementById("uploadForm");
    const fileInput = document.getElementById("fileInput");
    const tickerInput = document.getElementById("tickerInput");
    const resultDiv = document.getElementById("result");
    const summaryText = document.getElementById("summary");
    const dataChartCanvas = document.getElementById("dataChart");
    const clearButton = document.getElementById("clearButton");
    const reportList = document.getElementById("reportList");
    const toggleButton = document.getElementById("toggleButton");
    const reportListCollapse = document.getElementById("reportListCollapse");

    let dataChart;

    // Toggle icon for collapse button
    reportListCollapse.addEventListener("shown.bs.collapse", () => {
        toggleButton.innerHTML = '<i class="bi bi-chevron-up"></i>';
    });

    reportListCollapse.addEventListener("hidden.bs.collapse", () => {
        toggleButton.innerHTML = '<i class="bi bi-chevron-down"></i>';
    });

    // Function to display summary and chart
    function displaySummaryAndChart(summary, dataPoints, fileName) {
        summaryText.textContent = summary || "No summary available.";
        const labels = Object.keys(dataPoints);
        const values = Object.values(dataPoints);

        if (dataChart) {
            dataChart.destroy();
        }

        dataChart = new Chart(dataChartCanvas, {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: `Opening Prices for ${fileName}`,
                    data: values,
                    fill: false,
                    borderColor: "blue",
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { title: { display: true, text: "Date" } },
                    y: { title: { display: true, text: "Value" } }
                }
            }
        });

        resultDiv.style.display = "block";
        clearButton.style.display = "inline-block";

        // Save data to local storage to persist on page refresh
        localStorage.setItem("summary", summary);
        localStorage.setItem("dataPoints", JSON.stringify(dataPoints));
        localStorage.setItem("fileName", fileName);
    }

    // Load previous reports on page load
    async function loadPreviousReports() {
        try {
            const response = await fetch("../list_reports");
            const result = await response.json();
            reportList.innerHTML = "";

            result.reports.forEach(report => {
                const listItem = document.createElement("li");
                listItem.classList.add("list-group-item", "d-flex", "justify-content-between", "align-items-center");
                
                const reportText = document.createElement("span");
                reportText.textContent = report.file_name;
                reportText.classList.add("flex-grow-1");
                reportText.style.cursor = "pointer";
                reportText.addEventListener("click", () => loadReport(report.report_id, report.file_name));

                const deleteButton = document.createElement("button");
                deleteButton.classList.add("btn", "btn-danger", "btn-sm", "ms-2");
                deleteButton.innerHTML = '<i class="bi bi-trash"></i>';
                deleteButton.addEventListener("click", (event) => {
                    event.stopPropagation();
                    deleteReport(report.report_id);
                });

                listItem.appendChild(reportText);
                listItem.appendChild(deleteButton);
                reportList.appendChild(listItem);
            });
        } catch (error) {
            console.error("Failed to load previous reports:", error);
        }
    }

    // Delete report from server and update display
    async function deleteReport(reportId) {
        if (!confirm("Are you sure you want to delete this report? This action cannot be undone.")) return;

        try {
            const response = await fetch(`../delete_report/${reportId}`, { method: "DELETE" });
            if (response.ok) {
                loadPreviousReports(); // Refresh the list after deletion
                alert("Report deleted successfully");
            } else {
                alert("Failed to delete the report");
            }
        } catch (error) {
            console.error("Error deleting report:", error);
            alert("There was an error deleting the report. Please try again.");
        }
    }

    // Handle form submission
    uploadForm.addEventListener("submit", async function (event) {
        event.preventDefault();
        const file = fileInput.files[0];
        const ticker = tickerInput.value.trim();

        if (!file || file.type !== "application/pdf") {
            alert("Please select a valid PDF file.");
            return;
        }
        if (!ticker) {
            alert("Please enter a stock ticker symbol.");
            return;
        }

        const formData = new FormData();
        formData.append("file", file);
        formData.append("ticker", ticker);

        try {
            const response = await fetch("../process", { method: "POST", body: formData });
            const result = await response.json();
            displaySummaryAndChart(result.summary, result.data, ticker);
            loadPreviousReports();
        } catch (error) {
            console.error("Failed to upload the file:", error);
            alert("There was an error uploading the file. Please try again.");
        }
    });

    // Clear button to reset view
    clearButton.addEventListener("click", function () {
        uploadForm.reset();
        resultDiv.style.display = "none";
        clearButton.style.display = "none";
        if (dataChart) {
            dataChart.destroy();
        }

        localStorage.removeItem("summary");
        localStorage.removeItem("dataPoints");
        localStorage.removeItem("fileName");
        localStorage.removeItem("reportId");
    });

    // Load report from local storage on page load (for persistent data)
    function loadReportFromLocalStorage() {
        const summary = localStorage.getItem("summary");
        const dataPoints = JSON.parse(localStorage.getItem("dataPoints"));
        const fileName = localStorage.getItem("fileName");

        if (summary && dataPoints && fileName) {
            displaySummaryAndChart(summary, dataPoints, fileName);
        }
    }

    loadPreviousReports();
    loadReportFromLocalStorage();
});
