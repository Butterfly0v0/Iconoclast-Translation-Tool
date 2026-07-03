using System;
using System.IO;
using System.Text;

namespace CLI.ASCII_Interface
{
    internal class Main
    {
        public Main()
        {
            Console.CursorVisible = false;
            currentSelection = 0;

            Console.OutputEncoding = Encoding.UTF8;
            Console.InputEncoding = Encoding.UTF8;

            configF = new ConfigFile.Main();

            PrintHeader();
            PrintCommands();
        }

        private readonly string[] header = new[]{
                            @"  +----------------------------------------+",
                            @"  |      Iconoclast Translation Tool       |",
                            @"  |    Version 1.02 CN (Chinese support)   |",
                            @"  |         Modified for Chinese text      |",
                            @"  +----------------------------------------+",
                            @""
         };

        private readonly string[] commands = new[]{
                            @"         Use UP, DOWN and ENTER to move",
                            @"               through the menu.",
                            @""
         };

        private readonly string[] mainMenu = new[]{
                            @"  +----------------------------------------+",
                            @"       Extract text",
                            @"       Repack text",
                            @"       Copy dia from game",
                            @"       Change language file",
                            @"       Change Folder",
                            @"       Save options",
                            @"       Load options",
                            @"       Exit",
                            @"  +----------------------------------------+",
                            @""
         };

        private int currentSelection;

        private bool doAction = false;

        private readonly ConfigFile.Main configF;

        public void PrintHeader()
        {
            Console.WriteLine(string.Join("\n", header));
            Console.WriteLine($"  Current language file: {configF.Options.DiaFileName}");
            Console.WriteLine();
        }

        public void PrintCommands()
        {
            Console.WriteLine(string.Join("\n", commands));
        }

        public void PrintFullInterface(ConsoleKey keyPressedByUser)
        {
            Console.Clear();
            PrintHeader();
            PrintCommands();
            PrintMainMenu(keyPressedByUser);
        }

        public void PrintMainMenu(ConsoleKey keyPressedByUser)
        {
            doAction = false;

            UpdatePositionOrExecuteOption(keyPressedByUser, mainMenu.Length);

            PrintMenuAndHighlightFocusedOption(mainMenu);

            if (doAction)
            {
                ExecuteSelectedOption();
            }
        }

        private void PrintMenuAndHighlightFocusedOption(string[] menu)
        {
            for (int i = 0; i < menu.Length; i++)
            {
                if (i == currentSelection)
                {
                    Console.BackgroundColor = ConsoleColor.DarkYellow;
                    Console.ForegroundColor = ConsoleColor.Black;

                    StringBuilder sb = new StringBuilder(menu[i]);
                    sb[3] = '-';
                    sb[4] = '-';
                    sb[5] = '>';

                    Console.Write(sb.ToString() + "\n");
                    Console.ResetColor();
                }
                else
                {
                    Console.Write(mainMenu[i] + "\n");
                }
            }
        }

        private void UpdatePositionOrExecuteOption(ConsoleKey keyPressedByUser, int menuSize)
        {
            switch (keyPressedByUser)
            {
                case ConsoleKey.UpArrow:
                    {
                        currentSelection = (currentSelection == 1) ? menuSize - 3 : currentSelection - 1;
                        break;
                    }

                case ConsoleKey.DownArrow:
                    {
                        currentSelection = (currentSelection == menuSize - 3) ? 1 : currentSelection + 1;
                        break;
                    }

                case ConsoleKey.Enter:
                    {
                        doAction = true;
                        break;
                    }
            }
        }

        private void ExecuteSelectedOption()
        {
            switch (currentSelection)
            {
                case 1:
                    ExtractText();
                    break;
                case 2:
                    RepackText();
                    break;
                case 3:
                    configF.Options.CopyDiaFromGame();
                    break;
                case 4:
                    configF.Options.CycleDiaFileName();
                    break;
                case 5:
                    configF.Options.SetPoFolderPath();
                    break;
                case 6:
                    configF.SaveFile();
                    break;
                case 7:
                    configF.LoadFile();
                    break;
                default:
                    Environment.Exit(0);
                    break;
            }
        }

        private void ExtractText()
        {
            try
            {
                IO_ASCII.PrintOutput.EventMessage("Wait...");

                string diaPath = configF.Options.ResolveGameDiaPath();
                if (!File.Exists(diaPath))
                {
                    IO_ASCII.PrintOutput.ErrorMessage($"Could not find \"{diaPath}\". Use \"Copy dia from game\" first.");
                    return;
                }

                Iconoclast.Dia originalDiaFile = new Iconoclast.Dia(diaPath, configF.Options.DiaFileName);
                Iconoclast.PoFormat filePo = new Iconoclast.PoFormat(originalDiaFile.Speakers, originalDiaFile.Sentences, originalDiaFile.GameCode);
                Iconoclast.PoSpeaker newFilePoSpeaker = new Iconoclast.PoSpeaker(originalDiaFile.Speakers);
                filePo.MakePo();
                IO_ASCII.PrintOutput.EventMessage("Done!");
            }
            catch (Exception ex)
            {
                IO_ASCII.PrintOutput.ErrorMessage(ex.Message);
            }
        }

        private void RepackText()
        {
            try
            {
                IO_ASCII.PrintOutput.EventMessage("Wait...");

                Iconoclast.PoFormat translatedPo = new Iconoclast.PoFormat(Path.Combine("Extracted text", "Iconoclast.po"));
                Iconoclast.PoSpeaker filePoSpeaker = new Iconoclast.PoSpeaker();
                filePoSpeaker.ReadPo();
                Iconoclast.Dia newlDiaFile = new Iconoclast.Dia(
                    translatedPo.Speakers,
                    translatedPo.Sentences,
                    translatedPo.GameCode,
                    filePoSpeaker.TranslateSpeaker,
                    configF.Options.DiaFileName);

                IO_ASCII.PrintOutput.EventMessage($"Done! Output: Repacked File\\{configF.Options.DiaFileName}");
            }
            catch (Exception ex)
            {
                IO_ASCII.PrintOutput.ErrorMessage(ex.Message);
            }
        }
    }
}
