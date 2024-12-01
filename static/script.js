let socket = null;
let currentRoom = null;

document.getElementById("join-room").onclick = () => {
    const roomName = document.getElementById("room").value;
    if (roomName) {
        // Если комната уже подключена, не подключаем снова
        if (currentRoom === roomName) {
            console.log("Already connected to this room.");
            return;
        }

        currentRoom = roomName;
        socket = new WebSocket(`ws://${location.host}/ws/${currentRoom}`);

        socket.onopen = () => {
            console.log(`Joined room: ${currentRoom}`);
            document.getElementById("room-section").style.display = 'none';  // Скрываем форму после подключения
        };

        socket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log("Received from server:", data);  // Логируем полученные данные

            if (data.type === "message") {
                const messages = document.getElementById("messages");
                const messageElement = document.createElement("div");
                messageElement.textContent = `${data.id}: ${data.message}`;
                messages.appendChild(messageElement);
            } else if (data.type === "users") {
                const users = document.getElementById("users");
                users.textContent = `Online users: ${data.users.length}`;
            }
        };

        socket.onerror = (error) => {
            console.error("WebSocket Error:", error);
        };

        socket.onclose = (event) => {
            console.log("WebSocket connection closed:", event);
        };
    }
};

document.getElementById("send-button").onclick = () => {
    const input = document.getElementById("message-input");
    const message = input.value;
    if (message && socket) {
        socket.send(JSON.stringify({ type: "message", message }));
        input.value = "";
    }
};
