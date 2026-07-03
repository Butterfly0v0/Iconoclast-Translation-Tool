using System.IO;

namespace ConfigFile
{
    public class MainSettings
    {
        public string PoFolderPath { get; set; }

        /// <summary>
        /// Dialogue file to read/write: dia, diachn, diacht, etc.
        /// </summary>
        public string DiaFileName { get; set; } = "diachn";

        /// <summary>
        /// Path to the game's data folder containing dia* files.
        /// </summary>
        public string GameDataPath { get; set; } = "..\\data";

        public void SetPoFolderPath()
        {
            PoFolderPath = IO_ASCII.ReadInput.WaitForFolderPath("PO");
        }

        public void GetPoFolderPath()
        {
            if (string.IsNullOrEmpty(PoFolderPath) || !Directory.Exists(PoFolderPath) || Directory.GetFiles(PoFolderPath, "*.po", SearchOption.AllDirectories).Length == 0)
            {
                IO_ASCII.PrintOutput.ErrorMessage($"{PoFolderPath} folder not found or empty!\n");
                PoFolderPath = IO_ASCII.ReadInput.WaitForFolderPath("PO");
            }
        }

        public void CycleDiaFileName()
        {
            DiaFileName = DiaFileName switch
            {
                "dia" => "diachn",
                "diachn" => "diacht",
                "diacht" => "dia",
                _ => "diachn"
            };

            IO_ASCII.PrintOutput.EventMessage($"Language file set to \"{DiaFileName}\".");
        }

        public string ResolveGameDiaPath()
        {
            string localPath = DiaFileName;
            if (File.Exists(localPath))
            {
                return localPath;
            }

            string gamePath = Path.Combine(GameDataPath, DiaFileName);
            if (File.Exists(gamePath))
            {
                return gamePath;
            }

            return localPath;
        }

        public void CopyDiaFromGame()
        {
            string source = Path.Combine(GameDataPath, DiaFileName);

            if (!File.Exists(source))
            {
                IO_ASCII.PrintOutput.ErrorMessage($"Could not find \"{source}\".");
                return;
            }

            File.Copy(source, DiaFileName, overwrite: true);
            IO_ASCII.PrintOutput.EventMessage($"Copied \"{source}\" to \"{DiaFileName}\".");
        }
    }
}
