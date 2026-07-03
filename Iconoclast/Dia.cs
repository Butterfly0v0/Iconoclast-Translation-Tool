using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace Iconoclast
{
    public class Dia
    {
        private static readonly Encoding TextEncoding = Encoding.UTF8;

        private static readonly Regex IndexPlaceholderRegex = new Regex(@"\{#(\d+)\}", RegexOptions.Compiled);

        public List<string> Speakers { get; private set; }
        public List<string> Sentences { get; private set; }
        public List<string> GameCode { get; private set; }

        private readonly Rosetta Rose;

        private readonly System.Func<string, string> translateSpeaker;

        private readonly string outputFileName;

        public Dia(string filePath, string outputFileName = "dia")
        {
            this.outputFileName = outputFileName;

            if (File.Exists(filePath))
            {
                Speakers = new List<string>();
                Sentences = new List<string>();
                GameCode = new List<string>();

                Rose = new Rosetta();
                ExtractTestFromDia(filePath);
            }
        }

        public Dia(List<string> speak, List<string> senten, List<string> gameC, System.Func<string, string> translateSpeaker, string outputFileName = "dia")
        {
            Speakers = speak;
            Sentences = senten;
            GameCode = gameC;
            this.outputFileName = outputFileName;

            this.translateSpeaker = translateSpeaker;

            Rose = new Rosetta();
            BuildDia();
        }

        private void ExtractTestFromDia(string filePath)
        {
            using FileStream DiaFile = new FileStream(filePath, FileMode.Open, FileAccess.Read);
            using BinaryReader Br = new BinaryReader(DiaFile);
            int sentenceLenght = 0;

            DiaFile.Seek(0x06, SeekOrigin.Begin);

            Br.ReadInt32();

            while (DiaFile.Position != DiaFile.Length)
            {
                switch (Br.ReadInt32())
                {
                    case 1:
                        Br.ReadInt32();
                        sentenceLenght = Br.ReadInt32();
                        if (Sentences.Count == GameCode.Count)
                        {
                            Sentences.Add(ReadSingleLineFromDia(in DiaFile, sentenceLenght, true));
                        }
                        else
                        {
                            GameCode.Add(ReadSingleLineFromDia(in DiaFile, sentenceLenght, false, true));
                        }
                        Br.ReadByte();
                        break;
                    case 3:
                        Br.ReadInt64();
                        sentenceLenght = Br.ReadInt32();
                        Speakers.Add(ReadSingleLineFromDia(in DiaFile, sentenceLenght));
                        Br.ReadByte();
                        break;
                    default:
                        break;
                }
            }
        }

        private string ReadSingleLineFromDia(in FileStream DF, int sentenceLenght, bool isSentence = false, bool isGameCode = false)
        {
            byte[] tempBuffer = new byte[sentenceLenght - 1];
            DF.Read(tempBuffer, 0, tempBuffer.Length);
            string sentence = string.Empty;

            if (!isGameCode)
            {
                sentence = "|";
            }

            sentence += TextEncoding.GetString(tempBuffer);

            if (!isGameCode)
            {
                sentence = DecodeIndexedText(sentence);

                sentence = sentence.Replace("\\", "一");

                if (isSentence)
                {
                    sentence = sentence.Replace("{new}", "\n");
                }

                return sentence.Replace("|", string.Empty);
            }

            sentence = sentence.Replace("\\", "一");

            return sentence;
        }

        private static bool IsPlaceholderChar(string ch)
        {
            if (string.IsNullOrEmpty(ch))
            {
                return true;
            }

            if (ch == "?")
            {
                return true;
            }

            return ch.Length == 1 && ch[0] >= '\uE000' && ch[0] <= '\uF8FF';
        }

        private string DecodeIndexedText(string sentence)
        {
            for (int i = Rose.Stone.Length - 1; i >= 0; i--)
            {
                string ch = Rose.Stone[i];
                if (string.IsNullOrEmpty(ch))
                {
                    continue;
                }

                string replacement = IsPlaceholderChar(ch) ? "{#" + i + "}" : ch;
                sentence = sentence.Replace("|" + i.ToString(), replacement);
            }

            sentence = Regex.Replace(sentence, @"\|(\d+)(?=\||$)", "{#$1}");
            sentence = Regex.Replace(sentence, @"^(\d+)(?=\||$)", "{#$1}");

            return sentence.Replace("|", string.Empty);
        }

        public void BuildDia(string destinationDir = "Repacked File")
        {
            if (!Directory.Exists(destinationDir))
            {
                Directory.CreateDirectory(destinationDir);
            }

            string outputPath = Path.Combine(destinationDir, outputFileName);

            using FileStream newDia = new FileStream(outputPath, FileMode.Create, FileAccess.Write);
            using BinaryWriter Bw = new BinaryWriter(newDia);
            using BinaryWriter BwText = new BinaryWriter(newDia, TextEncoding);
            char[] tempS;

            Bw.Write(0x31525241);
            Bw.Write((short)0x302E);
            Bw.Write((uint)Sentences.Count);

            for (int i = 0; i < Sentences.Count; i++)
            {
                Bw.Write(0x03);
                Bw.Write(0x01);
                Bw.Write(0x02);

                if (string.IsNullOrEmpty(Speakers[i]))
                {
                    tempS = "".ToCharArray();
                }
                else
                {
                    string nameTranslated = translateSpeaker(Speakers[i]);
                    tempS = StringEncoder(nameTranslated).ToCharArray();
                }

                Bw.Write((uint)tempS.Length + 1);
                BwText.Write(tempS);
                Bw.Write((byte)0x0);

                Bw.Write(0x01);
                Bw.Write(0x02);

                tempS = StringEncoder(Sentences[i]).ToCharArray();
                Bw.Write((uint)tempS.Length + 1);
                BwText.Write(tempS);
                Bw.Write((byte)0x0);

                Bw.Write(0x01);
                Bw.Write(0x02);

                tempS = GameCode[i].Replace("一", "\\").ToCharArray();
                Bw.Write((uint)tempS.Length + 1);
                BwText.Write(tempS);
                Bw.Write((byte)0x0);
            }
        }

        private string StringEncoder(string sentence)
        {
            sentence = sentence.Replace("\n", "{new}");

            string encondedSentence = string.Empty;
            bool isCode = false;
            int i = 0;

            while (i < sentence.Length)
            {
                if (sentence[i] == '{' && i + 2 < sentence.Length && sentence[i + 1] == '#')
                {
                    Match match = IndexPlaceholderRegex.Match(sentence, i);
                    if (match.Success && match.Index == i)
                    {
                        if (isCode)
                        {
                            encondedSentence += match.Value;
                        }
                        else
                        {
                            encondedSentence += match.Groups[1].Value + "|";
                        }

                        i += match.Length;
                        continue;
                    }
                }

                char x = sentence[i];

                if (x == '{')
                {
                    isCode = true;
                }
                else if (x == '}')
                {
                    encondedSentence += "}|";
                    isCode = false;
                    i++;
                    continue;
                }

                if (isCode)
                {
                    if (encondedSentence.Length > 1 && x == '{' && encondedSentence[^1] == '一')
                    {
                        encondedSentence += '|';
                    }

                    encondedSentence += x;
                }
                else
                {
                    string ch = x.ToString();

                    if (!Rose.TryGetIndex(ch, out int pos))
                    {
                        throw new System.InvalidOperationException(
                            $"Character '{ch}' (U+{((int)x):X4}) is not in Rosetta.txt / Rosetta_CN.txt. " +
                            "Run build_rosetta_cn.py or keep the original {#index} placeholder.");
                    }

                    encondedSentence += pos.ToString() + "|";
                }

                i++;
            }

            if (encondedSentence.Length > 0 && encondedSentence[^1] == '|')
            {
                encondedSentence = encondedSentence.Remove(encondedSentence.Length - 1);
            }

            return encondedSentence.Replace("\\\\", "\\").Replace("一", "\\");
        }
    }
}
