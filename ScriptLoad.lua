local GameId = game.GameId
local Players = game:GetService("Players")
local TweenService = game:GetService("TweenService")
local HttpService = game:GetService("HttpService")
local TeleportService = game:GetService("TeleportService")
local CoreGui = game:GetService("CoreGui")
local Debris = game:GetService("Debris")
local StarterGui = game:GetService("StarterGui")
local ContentProvider = game:GetService("ContentProvider")

repeat task.wait() until game:IsLoaded() and Players.LocalPlayer
plr = Players.LocalPlayer

local isSupport = nil
local GameList = {
	[994732206] = "e4aedc7ccd2bacd83555baa884f3d4b1", -- Blox Fruit
	[7018190066] = "bf149e75708e91ad902bd72e408fae02", -- Dead Rails
	[383310974] = "b83e9255dc81e9392da975a89d26e363", -- Adopt Me
	[4777817887] = "35ad587b07c00b82c218fcf0e55eeea6", -- Blade Ball
	[5477548919] = "0a9bfef9eb03d0cb17dd85451e4be696", -- Honkai Star Rail Simulator
	[5750914919] = "b94343ca266a778e5da8d72e92d4aab5", -- Fisch
	[3359505957] = "095fbd843016a7af1d3a9ee88714c64a", -- Collect All Pets
	[6167925365] = "e220573a9f986e150c6af8d4d1fb9b7c", -- Cong Dong Viet Nam
	[5361032378] = "ff4e04500b94246eaa3f5c5be92a8b4a", -- Sol's RNG
	[7709344486] = "1d5eea7e66ccb5ca4d11c26ff2d4c6b1", -- Steal a Brainrot
	[7326934954] = "0aa67223637322085cfeaf80ae9af69f", -- 99 Nights in the Forest
	[3149100453] = "dbe59157859f6030587fd61ad4faad75", -- Eat Blob Simulator
	[5995470825] = "83363ffca1175ef0c06d4028b77061a4", -- Hypershot
	[358276974] = "23e50d188c7e27477a1c6eacb076e2ba", -- Apocalypse Rising 2
	[7541395924] = "c924e9543f9651c9cc1afabfe1f3de65", -- Build An Island
	[6701277882] = "1c48d56d18692670e5278e1df94997d8", -- Fish It
	[953622098] = "12933a8f18ec406f1ee26bbdc3b73abf", -- Word Bomb
	[7200297228] = "da7549d939f1a496dca0b8d3610196b5", -- Loot Hero
	[7832036655] = "456662bcac892ece28c0062bbe1a7a66", -- Arena Of Blox
	[7061783500] = "2fb6765dd4c0e2894dd107dd9e14c340", -- 2 Player Battle Tycoon
	[9619492068] = "85009d2e16759ccb0fc14e091f75eee3", -- Titan Fishing
	[9186719164] = "282f82c5fbcf3b438888268a4a5fa201", -- Sailor Piece
	[1451439645] = "282f82c5fbcf3b438888268a4a5fa201", -- King Legacy
	[3808081382] = "282f82c5fbcf3b438888268a4a5fa201", -- The Strongest Battleground
	[9338091695] = "282f82c5fbcf3b438888268a4a5fa201", -- Reign Piece
	[66654135] = "282f82c5fbcf3b438888268a4a5fa201", -- Murder Mystery 2
	[6331902150] = "282f82c5fbcf3b438888268a4a5fa201", -- Forsaken
	[8316902627] = "282f82c5fbcf3b438888268a4a5fa201", -- Plant vs Brainrot
	[7671049560] = "282f82c5fbcf3b438888268a4a5fa201", -- The Forge
	[9649298941] = "282f82c5fbcf3b438888268a4a5fa201", -- Survive LAVA for Brainrots!
	[9363735110] = "282f82c5fbcf3b438888268a4a5fa201", -- Escape Tsunami For Brainrot
	[9860860377] = "282f82c5fbcf3b438888268a4a5fa201", -- Anime Limitless
	[9073513091] = "282f82c5fbcf3b438888268a4a5fa201", -- Anime Apocalypse
	[9382839773] = "282f82c5fbcf3b438888268a4a5fa201", -- Lineage Piece
	[9917246399] = "282f82c5fbcf3b438888268a4a5fa201", -- Pirate Piece
	[10200395747] = "e21bc4d95b5db444bf19e8e03a664300", -- Grow A Garden 2
	[7395930870] = "ae046942f7060ae03fe7e55b5a60e8b6", -- Sell Lemons
	[9584852943] = "19a8c4cbd09697c8f9dbc9982ca10393", -- +1 Speed Keyboard Escape
}

for id, scriptid in pairs(GameList) do
	if id == GameId then
		isSupport = scriptid
	end
end

if _G.loadCustomId then
	isSupport = _G.loadCustomId
end

if not isSupport then
	loadstring(game:HttpGet('https://raw.githubusercontent.com/acsu123/HohoV2/refs/heads/main/ScriptLoadButOlder.lua'))()
	wait(9e9)
end

-- ================= BYPASS KEY & HWID =================
-- Cấu hình key giả để lừa Luarmor API (nếu API có check local)
_G.script_key = "HOHO_BYPASS"
getgenv().script_key = "HOHO_BYPASS"
script_key = "HOHO_BYPASS"

-- Thông báo load (có thể xóa nếu muốn)
StarterGui:SetCore("SendNotification", {
    Title = "HoHo Hub Bypass",
    Text = "Key & HWID Check Bypassed. Loading script...",
    Duration = 3,
    Icon = "rbxassetid://16276677105"
})

-- Gọi hàm tải script hack thật từ Luarmor (Luarmor sẽ tự xác thực bằng script_id vì đã có key giả)
local success, err = pcall(function()
    local api = loadstring(game:HttpGet("https://sdkapi-public.luarmor.net/library.lua"))()
    api.script_id = isSupport
    
    -- Ghi đè hàm check_key để nó luôn trả về Valid
    api.check_key = function(key)
        return {
            code = "KEY_VALID",
            message = "Bypass Activated",
            data = { 
                total_executions = 9999,
                note = "Bypass"
            }
        }
    end
    
    -- Gọi load script trực tiếp (bỏ qua UI check)
    api.load_script()
end)

if not success then
    StarterGui:SetCore("SendNotification", {
        Title = "HoHo Hub Bypass",
        Text = "Lỗi load script: " .. tostring(err),
        Duration = 5,
        Icon = "rbxassetid://16276677105"
    })
end