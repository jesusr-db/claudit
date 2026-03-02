import { HStack, Button } from "@chakra-ui/react";

const OPTIONS = [
  { label: "1h", value: 0.04 },
  { label: "1d", value: 1 },
  { label: "7d", value: 7 },
] as const;

interface TimeRangeSelectorProps {
  value: number;
  onChange: (days: number) => void;
}

export default function TimeRangeSelector({ value, onChange }: TimeRangeSelectorProps) {
  return (
    <HStack spacing={1}>
      {OPTIONS.map((opt) => (
        <Button
          key={opt.label}
          size="xs"
          variant={value === opt.value ? "solid" : "ghost"}
          colorScheme={value === opt.value ? "brand" : "gray"}
          fontWeight="600"
          fontSize="xs"
          px={3}
          borderRadius="full"
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </Button>
      ))}
    </HStack>
  );
}
