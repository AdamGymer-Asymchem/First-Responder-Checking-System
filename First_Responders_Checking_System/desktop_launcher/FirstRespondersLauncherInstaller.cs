using System;
using System.IO;
using System.Windows.Forms;

namespace FirstRespondersLauncherInstaller
{
    internal static class Program
    {
        [STAThread]
        private static void Main()
        {
            string sourceDir = AppDomain.CurrentDomain.BaseDirectory;
            string sourceLauncher = Path.Combine(sourceDir, "FirstRespondersRegister.exe");
            string sourceConfig = Path.Combine(sourceDir, "launcher-url.txt");

            if (!File.Exists(sourceLauncher))
            {
                MessageBox.Show(
                    "FirstRespondersRegister.exe was not found next to the installer.",
                    "Installer Error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return;
            }

            string installDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "FirstRespondersRegisterLauncher"
            );
            Directory.CreateDirectory(installDir);

            string installedLauncher = Path.Combine(installDir, "FirstRespondersRegister.exe");
            string installedConfig = Path.Combine(installDir, "launcher-url.txt");

            File.Copy(sourceLauncher, installedLauncher, true);

            if (File.Exists(sourceConfig))
            {
                File.Copy(sourceConfig, installedConfig, true);
            }
            else if (!File.Exists(installedConfig))
            {
                File.WriteAllText(installedConfig, "http://127.0.0.1:17000" + Environment.NewLine);
            }

            CreateShortcut(
                Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory),
                    "First Responders Register.lnk"
                ),
                installedLauncher
            );

            CreateShortcut(
                Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.Startup),
                    "First Responders Register.lnk"
                ),
                installedLauncher
            );

            MessageBox.Show(
                "Installed successfully.\r\n\r\n" +
                "Desktop shortcut created.\r\n" +
                "Startup shortcut created.\r\n\r\n" +
                "Update launcher-url.txt in the install folder if you need to point it at a different server.",
                "First Responders Register",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information
            );
        }

        private static void CreateShortcut(string shortcutPath, string targetPath)
        {
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            dynamic shell = Activator.CreateInstance(shellType);
            dynamic shortcut = shell.CreateShortcut(shortcutPath);
            shortcut.TargetPath = targetPath;
            shortcut.IconLocation = targetPath + ",0";
            shortcut.WorkingDirectory = Path.GetDirectoryName(targetPath);
            shortcut.WindowStyle = 1;
            shortcut.Description = "Launch the First Responders Register";
            shortcut.Save();
        }
    }
}
