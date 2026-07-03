using System.Collections.Generic;
using System.IO;
using System.Text;

namespace Iconoclast
{
    public class Rosetta
    {
        public string[] Stone { get; private set; }

        public Dictionary<string, int> CharToIndex { get; private set; }

        public Rosetta(string fileName = "Rosetta.txt")
        {
            if (File.Exists("Rosetta_CN.txt"))
            {
                Load("Rosetta_CN.txt");
            }
            else
            {
                Load(fileName);
            }
        }

        private void Load(string fileName)
        {
            using FileStream stream = new FileStream(fileName, FileMode.Open, FileAccess.Read);
            using StreamReader reader = new StreamReader(stream, Encoding.UTF8);

            string txt = reader.ReadToEnd();
            txt = txt.Replace("\r\n", "\n");
            if (txt.EndsWith("\n", System.StringComparison.Ordinal))
            {
                txt = txt[..^1];
            }

            Stone = txt.Split('\n');

            for (int i = 0; i < Stone.Length; i++)
            {
                Stone[i] = Stone[i].Trim('\r');
            }

            RebuildLookup();
        }

        private void RebuildLookup()
        {
            CharToIndex = new Dictionary<string, int>();

            for (int i = Stone.Length - 1; i >= 0; i--)
            {
                string ch = Stone[i];
                if (string.IsNullOrEmpty(ch))
                {
                    continue;
                }

                CharToIndex[ch] = i;
            }
        }

        public bool TryGetIndex(string character, out int index)
        {
            return CharToIndex.TryGetValue(character, out index);
        }
    }
}
