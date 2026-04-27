using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace FirstRespondersLauncher
{
    internal static class Program
    {
        private const string PlaceholderUrl = "http://127.0.0.1:17000";

        [STAThread]
        private static void Main()
        {
            string configDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "FirstRespondersRegisterLauncher"
            );
            string installedConfigPath = Path.Combine(configDir, "launcher-url.txt");
            string localConfigPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "launcher-url.txt");

            string url = ReadUrl(installedConfigPath);
            if (string.IsNullOrWhiteSpace(url))
            {
                url = ReadUrl(localConfigPath);
            }

            if (string.IsNullOrWhiteSpace(url))
            {
                url = PlaceholderUrl;
            }

            Uri parsedUri;
            if (!Uri.TryCreate(url, UriKind.Absolute, out parsedUri))
            {
                MessageBox.Show(
                    "The launcher URL is not valid. Update launcher-url.txt and try again.",
                    "First Responders Register",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }

            try
            {
                Process.Start(url);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "Unable to open the register URL.\r\n\r\n" + ex.Message,
                    "First Responders Register",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }

        private static string ReadUrl(string path)
        {
            if (!File.Exists(path))
            {
                return string.Empty;
            }

            string text = File.ReadAllText(path).Trim();
            return text;
        }
    }
}
