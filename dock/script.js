// Fetch stream status from Flask server and update the dock UI
function updateStatus(){
                fetch('http://localhost:5000/status')
                    .then(response => response.json())
                    .then(data => {
                        let html = ''

                        for (const [name, stats] of Object.entries(data)) {
                            // Determine indicator color based on stream state
                            let color
                            if (stats.active === true) color = 'green'
                            else if (stats.active === 'reconnecting') color = 'yellow'
                            else color = 'gray'

                            // Append platform icon SVG
                            if (name === "twitch")
                            html += `
                                <svg xmlns="http://www.w3.org/2000/svg" color="purple" width="20px" height="20px"   fill="currentColor" class="bi bi-twitch" viewBox="0 0 16 16">
                                    <path d="M3.857 0 1 2.857v10.286h3.429V16l2.857-2.857H9.57L14.714 8V0zm9.714 7.429-2.285 2.285H9l-2 2v-2H4.429V1.143h9.142z"/>
                                    <path d="M11.857 3.143h-1.143V6.57h1.143zm-3.143 0H7.571V6.57h1.143z"/>
                                </svg> ` 
                            else if (name === "tiktok")
                                html += `
                                <svg xmlns="http://www.w3.org/2000/svg" color="white" width="20px" height="20px"   fill="currentColor" class="bi bi-tiktok" viewBox="0 0 16 16">
                                    <path d="M9 0h1.98c.144.715.54 1.617 1.235 2.512C12.895 3.389 13.797 4 15 4v2c-1.753 0-3.07-.814-4-1.829V11a5 5 0 1 1-5-5v2a3 3 0 1 0 3 3z"/>
                                </svg>`
                            else if (name === "youtube")
                                html += `
                                <svg xmlns="http://www.w3.org/2000/svg" color="red" width="20px" height="20px"   fill="currentColor" class="bi bi-youtube" viewBox="0 0 16 16 ">
                                    <path d="M8.051 1.999h.089c.822.003 4.987.033 6.11.335a2.01 2.01 0 0 1 1.415 1.42c.101.38.172.883.22 1.402l.01.104.022.26.008.104c.065.914.073 1.77.074 1.957v.075c-.001.194-.01 1.108-.082 2.06l-.008.105-.009.104c-.05.572-.124 1.14-.235 1.558a2.01 2.01 0 0 1-1.415 1.42c-1.16.312-5.569.334-6.18.335h-.142c-.309 0-1.587-.006-2.927-.052l-.17-.006-.087-.004-.171-.007-.171-.007c-1.11-.049-2.167-.128-2.654-.26a2.01 2.01 0 0 1-1.415-1.419c-.111-.417-.185-.986-.235-1.558L.09 9.82l-.008-.104A31 31 0 0 1 0 7.68v-.123c.002-.215.01-.958.064-1.778l.007-.103.003-.052.008-.104.022-.26.01-.104c.048-.519.119-1.023.22-1.402a2.01 2.01 0 0 1 1.415-1.42c.487-.13 1.544-.21 2.654-.26l.17-.007.172-.006.086-.003.171-.007A100 100 0 0 1 7.858 2zM6.4 5.209v4.818l4.157-2.408z"/>
                                </svg>`
                            else if (name === "kick")
                                html += `
                                    <svg  xmlns="http://www.w3.org/2000/svg" width="20px" height="20px"  
                                        fill="currentColor" viewBox="0 0 24 24" >
                                        <!--Boxicons v3.0.8 https://boxicons.com | License  https://docs.boxicons.com/free-->
                                        <path d="M3.98 3h6.01v4h2V5h2V3H20v6.01h-2v2h-2v2h2v2h2v6.01h-6.01v-2h-2v-2h-2v4H3.98z"/>
                                    </svg>`
                            
                            // Append colored status dot and bitrate
                            html += ` <span style="color:${color}">● </span> <i class="bi bi-twitch"></i>`
                            if (stats.bitrate === "N/A") html += `bitrate: 0<br>`
                            else html += `bitrate: ${stats.bitrate} <br>`
                        }
                        platform.innerHTML = html
                    })
            }

            // Poll status every 3 seconds and run immediately on load
            setInterval(updateStatus, 3000)
            updateStatus()