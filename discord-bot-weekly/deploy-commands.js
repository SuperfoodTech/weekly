require('dotenv').config({ path: require('path').join(__dirname, '.env') });
const { REST, Routes } = require('discord.js');
const fs = require('fs');
const path = require('path');

const token = process.env.DISCORD_TOKEN;
let clientId = process.env.CLIENT_ID; // Application ID dari Developer Portal
if (!clientId && token) {
    try {
        const firstPart = token.split('.')[0];
        clientId = Buffer.from(firstPart, 'base64').toString('utf8');
        console.log(`[DEPLOY] Extracted CLIENT_ID from token: ${clientId}`);
    } catch (e) {
        console.error('Failed to extract CLIENT_ID from token:', e);
    }
}
const guildId = process.env.GUILD_ID;   // (Opsional) Server ID untuk mendaftarkan command secara instan di server tertentu

const commands = [];

// Membaca semua folder command
const commandsPath = path.join(__dirname, 'src', 'commands');
const commandFolders = fs.readdirSync(commandsPath);

for (const folder of commandFolders) {
    const folderPath = path.join(commandsPath, folder);
    
    if (fs.statSync(folderPath).isDirectory()) {
        const commandFiles = fs.readdirSync(folderPath).filter(file => file.endsWith('.js'));
        
        for (const file of commandFiles) {
            const filePath = path.join(folderPath, file);
            const command = require(filePath);
            if ('data' in command && 'execute' in command) {
                commands.push(command.data.toJSON());
            } else {
                console.log(`[WARNING] Command di ${filePath} tidak memiliki property "data" atau "execute".`);
            }
        }
    }
}

const rest = new REST({ version: '10' }).setToken(token);

(async () => {
    try {
        console.log(`Memulai proses pendaftaran ${commands.length} slash commands...`);

        // Mode Guild: mendaftarkan slash command spesifik ke server tertentu (Instan)
        // Jika ingin mendaftarkan global ke semua server, ganti bagian `Routes.applicationGuildCommands`
        // menjadi `Routes.applicationCommands(clientId)` dan hapus argumen guildId.
        const data = await rest.put(
            Routes.applicationGuildCommands(clientId, guildId),
            { body: commands },
        );

        console.log(`Berhasil mendaftarkan ${data.length} slash commands.`);
    } catch (error) {
        console.error('Terjadi kesalahan saat mendaftarkan command:', error);
    }
})();
