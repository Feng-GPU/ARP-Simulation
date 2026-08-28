[README.md](https://github.com/user-attachments/files/31543059/README.md)
# ARP 地址解析协议仿真软件

本项目模拟局域网内 ARP 请求广播、ARP 应答单播和 ARP 缓存维护过程。

## 环境准备

建议使用 Python 3.12 或更高版本：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

macOS/Linux 使用 `source .venv/bin/activate`，Windows 使用 `.venv\\Scripts\\activate`。

## 运行

macOS 可以直接在 Finder 中双击 `启动ARP仿真器.command`。

也可以使用终端：

```bash
python main.py
```

程序启动后默认创建 Host A～Host D 四台主机，最多可添加到六台。

## 测试

核心协议测试不需要显示器：

```bash
pytest -q
```

测试覆盖地址缓存生命周期、虚拟总线广播/单播以及完整 ARP 请求-应答流程。
