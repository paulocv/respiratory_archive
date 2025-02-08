// import './plotly_local'
// import { Plotly } from 'https://cdn.plot.ly/plotly-3.0.0.min.js'


function buildJurisdictionDropdowns() {
    console.groupCollapsed("buildJurisdictionDropdowns()")

    if (!juristiction_trace_index) {
        throw new Error("Object `juristiction_trace_index` is not defined")
    }

    // --- Loop over dropdowns
    for (const select of document.querySelectorAll('select.jurisdiction-select')) {
        console.log("Building options for dropdown:", select.id)

        let select_content = ""

        // --- Looop over jurisdictions in the dictionary
        for (const [key, traces] of Object.entries(juristiction_trace_index)){
            // select_content += `<option value="${key}">${key}</option>`
            if (key === "USA") {  // Default option
                select_content += `<option value="${key}" selected>${key}</option>`
            } else {
                select_content += `<option value="${key}">${key}</option>`
            }
        }

        select.innerHTML = select_content
    }

    console.groupEnd()
}

// Trigger for when the page loads
window.addEventListener("load", buildJurisdictionDropdowns)


function addMainJurisdictionListeners() {
    for (const disease_code of disease_codes){
        // let figDivId = document.getElementById(`${disease_code}-fig-div`)
        let select = document.getElementById(`${disease_code}-jurisdiction-select`)

        if (!select) {
            console.warn(
                `Element with id ${disease_code}-jurisdiction-select does not exist. 
                Dropdown events were not connected.`
            )
            continue
        }

        console.log(`Connecting dropdown changes to element: ${select.id}`)
        select.addEventListener(
            "input",
            function() {switchToJurisdiction(this.value, disease_code)}
        )


    }
}

window.addEventListener("load", addMainJurisdictionListeners)


function switchToJurisdiction(jurisdiction, diseaseCode) {
    // --- Input validation
    if (!juristiction_trace_index) {
        throw new Error("Object `juristiction_trace_index` is not defined")
    }

    if (!(disease_codes.includes(diseaseCode))) {
        throw new Error("Disease code must be one of 'c19', 'flu', 'rsv'")
    }

    if (!Object.keys(juristiction_trace_index).includes(jurisdiction)) {
        throw new Error(`Jurisdiction '${jurisdiction}' not found in jurisdiction_trace_index`)
    }

    // ====================

    // Match the figure element by disease code
    let figDivId = `${diseaseCode}-fig-div`
    let figDiv = document.getElementById(figDivId)
    if (!figDiv) {
        throw new Error(`Element with id ${figDivId} does not exist.`);
    }

    // --- Switch visibility of traces
    console.log(`Switching ${figDivId} to jurisdiction = ${jurisdiction}`)
    Plotly.restyle(figDiv, {visible: false})
    Plotly.restyle(figDiv, {visible: true}, juristiction_trace_index[jurisdiction])
}


function modifyDataSimple(divId) {
    let element = document.getElementById(divId)
    if (!element) {
        throw new Error(`Element with id ${divId} does not exist.`);
    }

    let data = element.data

    // Silly way to change data
    let trace_idx = 0
    let data_update = {
        name: "hahahaha",
        // y: data[trace_idx].y
    }
    Plotly.update(element, data_update, {}, trace_idx)
    // Plotly.restyle()

    console.log(element)
    // document.getElementById("demo").innerHTML = "Paragraph changed.";
}


