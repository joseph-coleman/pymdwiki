function runJupyterCode(button) {
    
    const container = button.parentElement.parentElement;
    const codeContainer = container.querySelector('.jupyter-code');
    const code = codeContainer.value;
    const outputArea = container.querySelector('.jupyter-output');
    const formattedCode = container.querySelector(".jupyter-formatted");
    const pageId = window.location.pathname; 

    // Clear previous output
    outputArea.textContent = "";
    
    // Disable button to prevent double-clicks
    button.disabled = true;
    var button_inner_text = button.innerText;
    button.innerText = "🚀";
    button.title = "Running..."

    // show output and hide formatted code
    formattedCode.style.display = "none";
    outputArea.style.display = "block";
    codeContainer.style.display = "none";

    const editButton = container.querySelector(".jupyter-edit");
    if (editButton.ariaPressed=="true"){
        editButton.ariaPressed = "false";
        update_formatted_code(button);
    }
    // 1. Open WebSocket Connection
    // Note: We use `window.location.host` to dynamically get the current server
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/run_jupyter`);

    // 2. On Open: Send the code payload
    ws.onopen = () => {
        ws.send(JSON.stringify({
            page_id: pageId,
            code: code
        }));
    };

    // 3. On Message: Append new text to the output area
    ws.onmessage = (event) => {
        //console.log(event);
        pymd_response = JSON.parse(event.data);
        //outputArea.innerHTML += event.data;
        if (pymd_response.hasOwnProperty("html") ) {
            outputArea.innerHTML += pymd_response.html;
        } else if (pymd_response.hasOwnProperty("js") ) {
            console.log("this getting picked up by webpage?")
            outputArea.innerHTML +=  pymd_response.js;
        }
        // Auto-scroll to bottom
        outputArea.scrollTop = outputArea.scrollHeight;
    };

    // 4. On Error
    ws.onerror = (error) => {
        outputArea.textContent += "\\n[Connection Error]";
        cleanup(button_inner_text);
    };

    // 5. On Close: Re-enable the button
    ws.onclose = () => {
        cleanup(button_inner_text);
    };

    function cleanup(button_inner_text) {
        button.disabled = false;
        button.innerText = button_inner_text;
        button.title = "Run"
        
    }
}
function runJupyterEdit(button){
    /* Make the text area visible so a person can edit code
       This does not update the original markdown document
        */
    const container = button.parentElement.parentElement;
    const codeContainer = container.querySelector('.jupyter-code');
    const outputArea = container.querySelector('.jupyter-output');
    const formattedCode = container.querySelector(".jupyter-formatted");

    if (button.ariaPressed=="true"){
        /* edit on -> off */
        button.ariaPressed = "false";

        update_formatted_code(button);

        formattedCode.style.display = "block";
        outputArea.style.display = "none";
        codeContainer.style.display = "none";

    } else {
        /* edit off -> on */
        button.ariaPressed = "true";
        formattedCode.style.display = "none";
        outputArea.style.display = "none";
        codeContainer.style.display = "block";
    }
}

async function update_formatted_code(button){
    const container = button.parentElement.parentElement;
    const codeContainer = container.querySelector('.jupyter-code');
    //const outputArea = container.querySelector('.jupyter-output');
    const formattedCode = container.querySelector(".jupyter-formatted");
    const code = codeContainer.value;

    const formData = new FormData();
    formData.append("code", code);

    const response = await fetch("/api/markdown/code/", {method:"POST", body: formData});
    const new_formmated_code = await response.text();
    
    formattedCode.innerHTML = new_formmated_code;
}

function runJupyterClear(button){
    /* Clear output and display markdown formatted code */
    const container = button.parentElement.parentElement;
    const codeContainer = container.querySelector('.jupyter-code');
    const outputArea = container.querySelector('.jupyter-output');
    const formattedCode = container.querySelector(".jupyter-formatted");
    outputArea.innerHTML = "";

    const editButton = container.querySelector(".jupyter-edit");
    editButton.ariaPressed = "false";

    // hide output and show formatted code
    formattedCode.style.display = "block";
    outputArea.style.display = "none";
    codeContainer.style.display = "none";

    // reset edited code?
    codeContainer.value = codeContainer.defaultValue;
    update_formatted_code(button);

}