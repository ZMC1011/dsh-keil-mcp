"""Tests for .uvprojx parsing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from keil_mcp_server.core.project_utils import count_source_files, parse_project

# minimal uvprojx in the official XML namespace
MINI_PROJ = '''<?xml version="1.0" encoding="UTF-8" standalone="no" ?>
<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="project_projx.xsd">
  <SchemaVersion>2.1</SchemaVersion>
  <Header>### uVision Project, (C) Keil Software</Header>
  <Targets>
    <Target>
      <TargetName>STM32F103C8</TargetName>
      <ToolsetNumber>0x4</ToolsetNumber>
      <TargetOption>
        <TargetCommonOption>
          <Device>STM32F103C8</Device>
          <Vendor>STMicroelectronics</Vendor>
          <PackID>Keil.STM32F1xx_DFP.2.4.1</PackID>
          <Cpu>IRAM(0x20000000,0x00005000) IROM(0x08000000,0x00040000) CPUTYPE("Cortex-M3") CLOCK(72000000)</Cpu>
        </TargetCommonOption>
      </TargetOption>
      <Groups>
        <Group>
          <GroupName>Source</GroupName>
          <Files>
            <File><FileName>main.c</FileName><FileType>1</FileType></File>
            <File><FileName>uart.c</FileName><FileType>1</FileType></File>
            <File><FileName>startup_stm32f103xb.s</FileName><FileType>2</FileType></File>
            <File><FileName>README.md</FileName><FileType>5</FileType></File>
          </Files>
        </Group>
      </Groups>
    </Target>
  </Targets>
</Project>
'''


def test_parse_mini_project(tmp_path):
    p = tmp_path / "mini.uvprojx"
    p.write_text(MINI_PROJ, encoding="utf-8")
    info = parse_project(p)
    assert info.device == "STM32F103C8"
    assert info.vendor == "STMicroelectronics"
    assert info.pack_id == "Keil.STM32F1xx_DFP.2.4.1"
    assert info.targets == ["STM32F103C8"]
    assert "Cortex-M3" in info.cpu
    assert info.groups == ["Source"]
    # only C/asm source files counted, README excluded
    assert set(info.source_files) == {"main.c", "uart.c", "startup_stm32f103xb.s"}
    assert count_source_files(p) == 3
